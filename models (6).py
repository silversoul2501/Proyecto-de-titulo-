from django.db import models
from django.contrib.auth import get_user_model
from rubricas.models import Descriptor, Checklist

User = get_user_model()

NIVELES = (
    ("L", "Logrado"),
    ("M", "Medianamente Logrado"),
    ("P", "Por Lograr"),
)

class Evaluacion(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.PROTECT, related_name="evaluaciones")
    evaluador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    evaluado = models.CharField(max_length=255, help_text="Persona/curso/contexto evaluado")
    fecha = models.DateField(auto_now_add=True)
    contexto = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=20, default="Borrador", choices=[("Borrador","Borrador"),("Cerrada","Cerrada")])
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"Eval {self.id} · {self.evaluado} · {self.fecha}"

    def get_progress(self):
        """
        Retorna una tupla (completed, total, percent) con el avance de la evaluación:
        - total: cantidad total de descriptores del checklist asociado
        - completed: respuestas con un nivel válido (L/M/P)
        - percent: porcentaje redondeado de avance
        """
        from rubricas.models import Descriptor

        try:
            total = Descriptor.objects.filter(foco__estandar__dominio__checklist=self.checklist).count()
        except Exception:
            total = Descriptor.objects.count()

        niveles_validos = [n[0] for n in NIVELES]  # ["L", "M", "P"]
        completed = self.respuestas.filter(nivel__in=niveles_validos).count()

        percent = round(completed * 100 / total) if total else 0
        return completed, total, percent

class RespuestaItem(models.Model):
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name="respuestas")
    descriptor = models.ForeignKey(Descriptor, on_delete=models.CASCADE)
    nivel = models.CharField(max_length=1, choices=NIVELES, blank=True)
    marcado = models.BooleanField(default=False)  # para modo checklist ✓/☐
    observaciones = models.TextField(blank=True)
    class Meta:
        unique_together = ("evaluacion", "descriptor")
    def __str__(self): return f"Resp {self.evaluacion_id} · desc {self.descriptor_id}"


# Evidencia: archivo/foto asociada a una respuesta de descriptor
class Evidencia(models.Model):
    """Archivo/foto asociada a una respuesta de descriptor."""
    respuesta = models.ForeignKey(RespuestaItem, related_name="evidencias", on_delete=models.CASCADE)
    archivo = models.FileField(upload_to="evidencias/%Y/%m/")
    nota = models.CharField(max_length=255, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        nombre = getattr(self.archivo, 'name', '')
        return f"Evidencia resp {self.respuesta_id} · {nombre}"