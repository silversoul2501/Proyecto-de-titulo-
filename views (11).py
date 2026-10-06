# ------------------------------------------------------------
# 📌 PENDIENTE FUTURO: GESTIÓN DE ELIMINACIÓN / ANULACIÓN
# ------------------------------------------------------------
# En versiones futuras se implementará una función para anular 
# o archivar evaluaciones sin borrarlas físicamente.
# Objetivos:
#  - Mantener trazabilidad de respuestas y evidencias.
#  - Permitir ocultar evaluaciones anuladas en la lista.
#  - Solo permitir eliminación definitiva de borradores vacíos.
# ------------------------------------------------------------


from django.template.loader import render_to_string
from django.db.models import Count, Q

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from rubricas.models import Checklist, Descriptor
from .models import Evaluacion, RespuestaItem, NIVELES, Evidencia

from xhtml2pdf import pisa
from django.template.loader import get_template
from io import BytesIO
import os
from django.contrib.staticfiles import finders


@login_required
def evaluacion_nueva(request):
    checklist = Checklist.objects.filter(activo=True).order_by("-version").first()
    if not checklist:
        return HttpResponseBadRequest("No hay checklist activo.")
    ev = Evaluacion.objects.create(
        checklist=checklist,
        evaluador=request.user if request.user.is_authenticated else None,
        evaluado="Demo",
        estado="Borrador",
    )
    return redirect("evaluaciones:editar", pk=ev.pk)


# ---- Listado de evaluaciones con filtro y búsqueda ----
@login_required
def evaluacion_lista(request):
    """Listado con filtro por estado y búsqueda por Docente/Curso."""
    qs = Evaluacion.objects.all().order_by("-id")

    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()

    if q:
        qs = qs.filter(Q(evaluado__icontains=q) | Q(contexto__icontains=q))
    if estado in ("Borrador", "Cerrada"):
        qs = qs.filter(estado=estado)

    paginator = Paginator(qs, 20)  # 20 por página
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "estado": estado,
    }
    return render(request, "evaluaciones/lista.html", ctx)


@login_required
@require_POST
def evaluacion_finalizar(request, pk):
    ev = get_object_or_404(Evaluacion, pk=pk)

    # Validación estricta: 100% de descriptores con nivel
    completed, total, percent = ev.get_progress()
    if completed < total:
        faltan = total - completed
        messages.error(request, f"No se puede finalizar: faltan {faltan} de {total} descriptores por definir nivel.")
        return redirect("evaluaciones:editar", pk=pk)

    # Validación de metadatos mínimos
    if not ev.evaluado or not ev.contexto:
        messages.error(request, "Completa Docente y Curso/Contexto antes de finalizar.")
        return redirect("evaluaciones:editar", pk=pk)

    if ev.estado != "Cerrada":
        ev.estado = "Cerrada"
        ev.save(update_fields=["estado"])  # sólo cambia estado
        messages.success(request, "Evaluación finalizada correctamente.")

    return redirect("evaluaciones:editar", pk=pk)


# ---- Nuevas vistas: reabrir y actualizar meta ----

@login_required
@require_POST
def evaluacion_reabrir(request, pk):
    """Cambia el estado de Cerrada -> Borrador para permitir nuevas ediciones."""
    ev = get_object_or_404(Evaluacion, pk=pk)
    if ev.estado == "Cerrada":
        ev.estado = "Borrador"
        ev.save(update_fields=["estado"])  # updated_at se actualizará automáticamente
        messages.success(request, "Evaluación reabierta correctamente.")
    return redirect("evaluaciones:editar", pk=pk)


@login_required
@require_POST
def evaluacion_actualizar_meta(request, pk):
    """Actualiza datos generales de la evaluación (docente y curso) cuando está en Borrador."""
    ev = get_object_or_404(Evaluacion, pk=pk)
    if ev.estado == "Cerrada":
        return HttpResponseBadRequest("Evaluación cerrada")
    evaluado = request.POST.get("evaluado", "").strip()
    contexto = request.POST.get("contexto", "").strip()
    # Permitir dejar alguno vacío si el usuario no lo completa; guarda lo que venga
    ev.evaluado = evaluado or ev.evaluado
    ev.contexto = contexto or ev.contexto
    ev.save(update_fields=["evaluado", "contexto"])  # updated_at se actualiza por auto_now
    return redirect("evaluaciones:editar", pk=pk)


@login_required
def evaluacion_editar(request, pk):
    ev = get_object_or_404(Evaluacion, pk=pk)
    descriptores = Descriptor.objects.select_related("foco__estandar__dominio").order_by(
        "foco__estandar__dominio__orden",
        "foco__estandar__orden",
        "foco__orden",
        "orden",
        "id",
    )
    respuestas = {r.descriptor_id: r for r in ev.respuestas.select_related("descriptor").all()}
    for d in descriptores:
        d.resp = respuestas.get(d.id)
    ctx = {
        "ev": ev,
        "descriptores": descriptores,
        "respuestas": respuestas,
        "NIVELES": NIVELES,
        "readonly": ev.estado == "Cerrada",
        "docentes": settings.DOCENTES_PREDEFINIDOS,
    }
    completed, total, percent = ev.get_progress()
    ctx.update({
        "progress_completed": completed,
        "progress_total": total,
        "progress_percent": percent,
    })
    return render(request, "evaluaciones/form_eval.html", ctx)


@login_required
@require_POST
def respuesta_guardar(request, pk, descriptor_id):
    ev = get_object_or_404(Evaluacion, pk=pk)
    if ev.estado == "Cerrada":
        return HttpResponseBadRequest("Evaluación cerrada")
    descriptor = get_object_or_404(Descriptor, pk=descriptor_id)
    nivel = request.POST.get("nivel", "").strip()
    if nivel == "-":
        nivel = ""
    marcado = request.POST.get("marcado") == "on"
    obs = request.POST.get("observaciones", "").strip()
    if nivel and nivel not in dict(NIVELES):
        return HttpResponseBadRequest("Nivel inválido.")
    resp, _ = RespuestaItem.objects.get_or_create(evaluacion=ev, descriptor=descriptor)
    resp.nivel = nivel
    resp.marcado = marcado
    resp.observaciones = obs
    resp.save()
    # Ensure descriptor reflects the updated response
    descriptor.resp = resp
    descriptor_html = render_to_string(
        "evaluaciones/_fila_descriptor.html",
        {"d": descriptor, "resp": resp, "NIVELES": NIVELES, "ev": ev},
        request=request,
    )
    completed, total, percent = ev.get_progress()
    progress_html = render_to_string(
        "evaluaciones/_progress.html",
        {
            "ev": ev,
            "progress_completed": completed,
            "progress_total": total,
            "progress_percent": percent,
        },
        request=request,
    )
    return HttpResponse(descriptor_html + progress_html)


# Resumen endpoint: agregados por Dominio y Estándar
@login_required
def evaluacion_resumen(request, pk):
    ev = get_object_or_404(Evaluacion, pk=pk)
    qs = ev.respuestas.select_related("descriptor__foco__estandar__dominio")

    # --- Agregados por Dominio ---
    por_dom_qs = (
        qs.values(
            "descriptor__foco__estandar__dominio__id",
            "descriptor__foco__estandar__dominio__nombre",
        )
        .annotate(
            total=Count("id"),
            l=Count("id", filter=Q(nivel="L")),
            m=Count("id", filter=Q(nivel="M")),
            p=Count("id", filter=Q(nivel="P")),
        )
        .order_by("descriptor__foco__estandar__dominio__id")
    )

    por_dom = []
    tot_dom_total = tot_dom_l = tot_dom_m = tot_dom_p = 0
    for r in por_dom_qs:
        total = r.get("total") or 0
        l = r.get("l") or 0
        m = r.get("m") or 0
        p = r.get("p") or 0
        r["pct_l"] = round(l * 100 / total) if total else 0
        r["pct_m"] = round(m * 100 / total) if total else 0
        r["pct_p"] = round(p * 100 / total) if total else 0
        por_dom.append(r)
        tot_dom_total += total
        tot_dom_l += l
        tot_dom_m += m
        tot_dom_p += p

    tot_dom = {
        "total": tot_dom_total,
        "l": tot_dom_l,
        "m": tot_dom_m,
        "p": tot_dom_p,
        "pct_l": round(tot_dom_l * 100 / tot_dom_total) if tot_dom_total else 0,
        "pct_m": round(tot_dom_m * 100 / tot_dom_total) if tot_dom_total else 0,
        "pct_p": round(tot_dom_p * 100 / tot_dom_total) if tot_dom_total else 0,
    }

    # --- Agregados por Estándar ---
    por_est_qs = (
        qs.values(
            "descriptor__foco__estandar__id",
            "descriptor__foco__estandar__nombre",
            "descriptor__foco__estandar__dominio__nombre",
        )
        .annotate(
            total=Count("id"),
            l=Count("id", filter=Q(nivel="L")),
            m=Count("id", filter=Q(nivel="M")),
            p=Count("id", filter=Q(nivel="P")),
        )
        .order_by(
            "descriptor__foco__estandar__dominio__nombre",
            "descriptor__foco__estandar__id",
        )
    )

    por_est = []
    tot_est_total = tot_est_l = tot_est_m = tot_est_p = 0
    for r in por_est_qs:
        total = r.get("total") or 0
        l = r.get("l") or 0
        m = r.get("m") or 0
        p = r.get("p") or 0
        r["pct_l"] = round(l * 100 / total) if total else 0
        r["pct_m"] = round(m * 100 / total) if total else 0
        r["pct_p"] = round(p * 100 / total) if total else 0
        por_est.append(r)
        tot_est_total += total
        tot_est_l += l
        tot_est_m += m
        tot_est_p += p

    tot_est = {
        "total": tot_est_total,
        "l": tot_est_l,
        "m": tot_est_m,
        "p": tot_est_p,
        "pct_l": round(tot_est_l * 100 / tot_est_total) if tot_est_total else 0,
        "pct_m": round(tot_est_m * 100 / tot_est_total) if tot_est_total else 0,
        "pct_p": round(tot_est_p * 100 / tot_est_total) if tot_est_total else 0,
    }

    return render(
        request,
        "evaluaciones/resumen.html",
        {
            "ev": ev,
            "por_dom": por_dom,
            "por_est": por_est,
            "tot_dom": tot_dom,
            "tot_est": tot_est,
        },
    )

# Exportar resumen a PDF (xhtml2pdf)
@login_required
def evaluacion_pdf(request, pk):
    ev = get_object_or_404(Evaluacion, pk=pk)
    qs = ev.respuestas.select_related("descriptor__foco__estandar__dominio")

    # --- Agregados por Dominio --- (mismos cálculos que evaluacion_resumen)
    por_dom_qs = (
        qs.values(
            "descriptor__foco__estandar__dominio__id",
            "descriptor__foco__estandar__dominio__nombre",
        )
        .annotate(
            total=Count("id"),
            l=Count("id", filter=Q(nivel="L")),
            m=Count("id", filter=Q(nivel="M")),
            p=Count("id", filter=Q(nivel="P")),
        )
        .order_by("descriptor__foco__estandar__dominio__id")
    )

    por_dom = []
    tot_dom_total = tot_dom_l = tot_dom_m = tot_dom_p = 0
    for r in por_dom_qs:
        total = r.get("total") or 0
        l = r.get("l") or 0
        m = r.get("m") or 0
        p = r.get("p") or 0
        r["pct_l"] = round(l * 100 / total) if total else 0
        r["pct_m"] = round(m * 100 / total) if total else 0
        r["pct_p"] = round(p * 100 / total) if total else 0
        por_dom.append(r)
        tot_dom_total += total
        tot_dom_l += l
        tot_dom_m += m
        tot_dom_p += p

    tot_dom = {
        "total": tot_dom_total,
        "l": tot_dom_l,
        "m": tot_dom_m,
        "p": tot_dom_p,
        "pct_l": round(tot_dom_l * 100 / tot_dom_total) if tot_dom_total else 0,
        "pct_m": round(tot_dom_m * 100 / tot_dom_total) if tot_dom_total else 0,
        "pct_p": round(tot_dom_p * 100 / tot_dom_total) if tot_dom_total else 0,
    }

    # --- Agregados por Estándar ---
    por_est_qs = (
        qs.values(
            "descriptor__foco__estandar__id",
            "descriptor__foco__estandar__nombre",
            "descriptor__foco__estandar__dominio__nombre",
        )
        .annotate(
            total=Count("id"),
            l=Count("id", filter=Q(nivel="L")),
            m=Count("id", filter=Q(nivel="M")),
            p=Count("id", filter=Q(nivel="P")),
        )
        .order_by(
            "descriptor__foco__estandar__dominio__nombre",
            "descriptor__foco__estandar__id",
        )
    )

    por_est = []
    tot_est_total = tot_est_l = tot_est_m = tot_est_p = 0
    for r in por_est_qs:
        total = r.get("total") or 0
        l = r.get("l") or 0
        m = r.get("m") or 0
        p = r.get("p") or 0
        r["pct_l"] = round(l * 100 / total) if total else 0
        r["pct_m"] = round(m * 100 / total) if total else 0
        r["pct_p"] = round(p * 100 / total) if total else 0
        por_est.append(r)
        tot_est_total += total
        tot_est_l += l
        tot_est_m += m
        tot_est_p += p

    tot_est = {
        "total": tot_est_total,
        "l": tot_est_l,
        "m": tot_est_m,
        "p": tot_est_p,
        "pct_l": round(tot_est_l * 100 / tot_est_total) if tot_est_total else 0,
        "pct_m": round(tot_est_m * 100 / tot_est_total) if tot_est_total else 0,
        "pct_p": round(tot_est_p * 100 / tot_est_total) if tot_est_total else 0,
    }

    context = {
        "ev": ev,
        "por_dom": por_dom,
        "por_est": por_est,
        "tot_dom": tot_dom,
        "tot_est": tot_est,
    }

    # Resolver rutas de estáticos y media para xhtml2pdf
    def link_callback(uri, rel):
        # STATIC
        if uri.startswith(settings.STATIC_URL):
            path = uri.replace(settings.STATIC_URL, "")
            absolute = finders.find(path)
            if isinstance(absolute, (list, tuple)):
                absolute = absolute[0]
            return absolute or uri
        # MEDIA
        if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
            return os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        # Cualquier otra ruta
        return uri

    # Render del template PDF
    template = get_template("evaluaciones/pdf_resumen.html")
    html = template.render(context, request=request)

    # Generar PDF con xhtml2pdf
    result = BytesIO()
    pdf = pisa.CreatePDF(src=html, dest=result, link_callback=link_callback, encoding="UTF-8")
    if pdf.err:
        return HttpResponse("Error generando PDF", status=500)

    response = HttpResponse(result.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Resumen_Evaluacion_{ev.id}.pdf"'
    return response


# ---- Evidencias: subir y borrar ----

@login_required
@require_POST
def evidencia_subir(request, pk, respuesta_id):
    """Sube una evidencia (archivo + nota) a una RespuestaItem.
    Devuelve la fila de descriptor renderizada + progreso (HTMX-ready).
    """
    ev = get_object_or_404(Evaluacion, pk=pk)
    if ev.estado == "Cerrada":
        return HttpResponseBadRequest("Evaluación cerrada")

    resp = get_object_or_404(RespuestaItem, pk=respuesta_id, evaluacion=ev)
    f = request.FILES.get("archivo")
    nota = request.POST.get("nota", "").strip()
    if not f:
        return HttpResponseBadRequest("Archivo requerido")

    # Validaciones: tamaño y tipo
    max_bytes = 10 * 1024 * 1024  # 10 MB
    if getattr(f, "size", 0) > max_bytes:
        return HttpResponseBadRequest("Archivo demasiado grande (máx. 10 MB).")

    nombre = getattr(f, "name", "")
    ext = os.path.splitext(nombre)[1].lower()
    allowed_ext = {".pdf", ".png", ".jpg", ".jpeg"}
    if ext not in allowed_ext:
        return HttpResponseBadRequest("Tipo de archivo no permitido. Usa PDF, JPG o PNG.")

    # (Opcional) validar por content-type si viene informado por el navegador
    allowed_ct = {"application/pdf", "image/png", "image/jpeg"}
    ct = getattr(f, "content_type", None)
    if ct and ct not in allowed_ct:
        return HttpResponseBadRequest("Tipo de archivo no permitido por content-type.")

    Evidencia.objects.create(respuesta=resp, archivo=f, nota=nota)

    # Renderizar la fila completa del descriptor + progreso
    descriptor = resp.descriptor
    descriptor.resp = resp
    descriptor_html = render_to_string(
        "evaluaciones/_fila_descriptor.html",
        {"d": descriptor, "resp": resp, "NIVELES": NIVELES, "ev": ev},
        request=request,
    )
    completed, total, percent = ev.get_progress()
    progress_html = render_to_string(
        "evaluaciones/_progress.html",
        {
            "ev": ev,
            "progress_completed": completed,
            "progress_total": total,
            "progress_percent": percent,
        },
        request=request,
    )
    return HttpResponse(descriptor_html + progress_html)


@login_required
@require_POST
def evidencia_borrar(request, eid):
    """Elimina una evidencia por id y devuelve la fila + progreso actualizados."""
    evd = get_object_or_404(Evidencia, pk=eid)
    ev = evd.respuesta.evaluacion
    if ev.estado == "Cerrada":
        return HttpResponseBadRequest("Evaluación cerrada")

    resp = evd.respuesta
    descriptor = resp.descriptor
    evd.delete()

    # Renderizar la fila de descriptor + progreso
    descriptor.resp = resp
    descriptor_html = render_to_string(
        "evaluaciones/_fila_descriptor.html",
        {"d": descriptor, "resp": resp, "NIVELES": NIVELES, "ev": ev},
        request=request,
    )
    completed, total, percent = ev.get_progress()
    progress_html = render_to_string(
        "evaluaciones/_progress.html",
        {
            "ev": ev,
            "progress_completed": completed,
            "progress_total": total,
            "progress_percent": percent,
        },
        request=request,
    )
    return HttpResponse(descriptor_html + progress_html)