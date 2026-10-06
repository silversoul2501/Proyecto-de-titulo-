from django.db import models

class TimeStampedModel(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Dominio(TimeStampedModel):
    nombre = models.CharField(max_length=255, unique=True)
    orden = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["orden", "id"]
    def __str__(self): return self.nombre

class Estandar(TimeStampedModel):
    dominio = models.ForeignKey(Dominio, on_delete=models.CASCADE, related_name="estandares")
    nombre = models.CharField(max_length=255)
    orden = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = ("dominio", "nombre")
        ordering = ["dominio__orden", "orden", "id"]
    def __str__(self): return self.nombre

class Foco(TimeStampedModel):
    estandar = models.ForeignKey(Estandar, on_delete=models.CASCADE, related_name="focos")
    nombre = models.CharField(max_length=255)
    orden = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = ("estandar", "nombre")
        ordering = ["estandar__dominio__orden", "estandar__orden", "orden", "id"]
    def __str__(self): return self.nombre

class Descriptor(TimeStampedModel):
    foco = models.ForeignKey(Foco, on_delete=models.CASCADE, related_name="descriptores")
    texto = models.TextField()
    logrado = models.TextField(blank=True, null=True)
    medianamente_logrado = models.TextField(blank=True, null=True)
    por_lograr = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = [
            "foco__estandar__dominio__orden",
            "foco__estandar__orden",
            "foco__orden",
            "orden",
            "id",
        ]
        unique_together = ("foco", "texto")
    def __str__(self): return self.texto[:80]

# Plantillas/Checklist versionables
class Checklist(TimeStampedModel):
    nombre = models.CharField(max_length=255, default="Plantilla MBE")
    version = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)
    class Meta:
        unique_together = ("nombre", "version")
        ordering = ["-activo", "-version", "id"]
    def __str__(self): return f"{self.nombre} v{self.version}"

class ChecklistItem(TimeStampedModel):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    descriptor = models.ForeignKey(Descriptor, on_delete=models.CASCADE, related_name="checklists")
    orden = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = ("checklist", "descriptor")
        ordering = ["orden", "id"]
    def __str__(self): return f"{self.checklist} · {self.descriptor_id}"