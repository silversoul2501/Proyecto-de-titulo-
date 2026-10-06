import csv
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from rubricas.models import Dominio, Estandar, Foco, Descriptor, Checklist, ChecklistItem
import re

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    # Tratar valores 'nan'/'null'/'none' como vacío
    if s.lower() in {"nan", "null", "none"}:
        return ""
    # Colapsar espacios múltiples
    s = re.sub(r"\s+", " ", s)
    return s

class Command(BaseCommand):
    help = "Importa rúbrica jerárquica desde CSV y crea Checklist v1 con todos los descriptores."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, default="rubricas/data/rubrica_normalizada.csv")
        parser.add_argument("--rebuild", action="store_true", help="Borra y reconstruye toda la jerarquía antes de importar")

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv"])
        # Intentar varias ubicaciones razonables
        candidates = [
            csv_path,
            Path("rubricas/data/rubrica_normalizada.csv"),
            Path.cwd() / "rubricas" / "data" / "rubrica_normalizada.csv",
            Path.home() / "Desktop" / "rubrica_normalizada.csv",
            Path.cwd() / "rubrica_normalizada.csv",
        ]
        chosen = None
        for p in candidates:
            if p.exists():
                chosen = p
                break
        if not chosen:
            raise CommandError(
                "No se encontró el archivo CSV. Prueba con:\n"
                "  python manage.py import_rubrica --csv /Users/edu/Desktop/rubrica_normalizada.csv\n"
                f"Intentado (sin éxito): {', '.join(str(c) for c in candidates)}"
            )
        csv_path = chosen
        self.stdout.write(self.style.NOTICE(f"Importando desde: {csv_path}"))

        from django.db import transaction
        if opts.get("rebuild"):
            self.stdout.write(self.style.WARNING("REBUILD: borrando datos existentes de rúbrica..."))
            with transaction.atomic():
                ChecklistItem.objects.all().delete()
                Checklist.objects.all().delete()
                Descriptor.objects.all().delete()
                Foco.objects.all().delete()
                Estandar.objects.all().delete()
                Dominio.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("REBUILD: tablas vaciadas."))

        counts = dict(dominio=0, estandar=0, foco=0, descriptor=0)
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalizar y forward-fill jerarquía
                dom_raw = _norm(row.get("DOMINIO"))
                est_raw = _norm(row.get("ESTANDAR"))
                foc_raw = _norm(row.get("FOCO"))
                desc = _norm(row.get("DESCRIPTOR"))
                logrado = _norm(row.get("LOGRADO"))
                med = _norm(row.get("MEDIANAMENTE LOGRADO"))
                por = _norm(row.get("POR LOGRAR"))

                # Forward-fill: si viene vacío, reutiliza el último no vacío
                # Mantén estado fuera del bucle: last_dom/last_est/last_foc
                try:
                    orden = int(_norm(row.get("orden")) or 0)
                except Exception:
                    orden = 0

                # Inicializa los últimos valores si no existen en locals()
                if "last_dom" not in locals():
                    last_dom = ""
                if "last_est" not in locals():
                    last_est = ""
                if "last_foc" not in locals():
                    last_foc = ""

                dom = dom_raw or last_dom
                est = est_raw or last_est
                foc = foc_raw or last_foc

                # Si aún faltan jerarquías o el descriptor está vacío, salta la fila
                if not (dom and est and foc and desc):
                    continue

                # Actualiza last_*
                last_dom, last_est, last_foc = dom, est, foc

                dominio, c = Dominio.objects.get_or_create(nombre=dom, defaults={"orden": orden})
                counts["dominio"] += int(c)
                estandar, c = Estandar.objects.get_or_create(dominio=dominio, nombre=est, defaults={"orden": orden})
                counts["estandar"] += int(c)
                foco, c = Foco.objects.get_or_create(estandar=estandar, nombre=foc, defaults={"orden": orden})
                counts["foco"] += int(c)

                descriptor, c = Descriptor.objects.get_or_create(
                    foco=foco, texto=desc,
                    defaults={
                        "logrado": logrado or None,
                        "medianamente_logrado": med or None,
                        "por_lograr": por or None,
                        "orden": orden,
                    }
                )
                if not c:
                    changed = False
                    if descriptor.logrado != (logrado or None):
                        descriptor.logrado = logrado or None; changed = True
                    if descriptor.medianamente_logrado != (med or None):
                        descriptor.medianamente_logrado = med or None; changed = True
                    if descriptor.por_lograr != (por or None):
                        descriptor.por_lograr = por or None; changed = True
                    if descriptor.orden != orden:
                        descriptor.orden = orden; changed = True
                    if changed:
                        descriptor.save()
                counts["descriptor"] += int(c)

        checklist, _ = Checklist.objects.get_or_create(nombre="Plantilla MBE", version=1, defaults={"activo": True})
        if not checklist.items.exists():
            items = [
                ChecklistItem(checklist=checklist, descriptor=d, orden=d.orden)
                for d in Descriptor.objects.order_by("orden", "id")
            ]
            ChecklistItem.objects.bulk_create(items, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"OK · Importados/actualizados: {counts}"))
        self.stdout.write(self.style.SUCCESS(f"Checklist: {checklist} · Ítems: {checklist.items.count()}"))