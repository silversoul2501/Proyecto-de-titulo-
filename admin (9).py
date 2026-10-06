from django.contrib import admin
# Personalización del panel de administración
admin.site.site_header = "Panel de Administración — Sistema de Evaluaciones Docentes"
admin.site.index_title = "Gestión interna"
admin.site.site_title = "Evaluaciones MBE"
# Usar un index personalizado para añadir un botón hacia el sistema
admin.site.index_template = "admin/custom_index.html"
admin.site.site_url = "/evaluaciones/"
from .models import Evaluacion, RespuestaItem, Evidencia

class EvidenciaInline(admin.TabularInline):
    model = Evidencia
    extra = 0

class RespuestaInline(admin.TabularInline):
    model = RespuestaItem
    extra = 0
    show_change_link = True
    readonly_fields = ("evidencias_count",)
    fields = ("descriptor", "nivel", "marcado", "observaciones", "evidencias_count")

    def evidencias_count(self, obj):
        return obj.evidencias.count()
    evidencias_count.short_description = "Evidencias"

@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("id","checklist","evaluado","fecha","estado")
    list_filter = ("estado","fecha","checklist")
    search_fields = ("evaluado","contexto")
    inlines = [RespuestaInline]

@admin.register(RespuestaItem)
class RespuestaItemAdmin(admin.ModelAdmin):
    list_display = ("id", "evaluacion", "descriptor", "nivel", "marcado")
    list_filter = ("nivel", "marcado")
    search_fields = ("evaluacion__evaluado", "descriptor__nombre", "observaciones")
    inlines = [EvidenciaInline]