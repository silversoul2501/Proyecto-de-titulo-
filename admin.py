from django.contrib import admin
from .models import Dominio, Estandar, Foco, Descriptor, Checklist, ChecklistItem

@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ("id","nombre","orden","creado_en")
    search_fields = ("nombre",)
    ordering = ("orden",)

@admin.register(Estandar)
class EstandarAdmin(admin.ModelAdmin):
    list_display = ("id","nombre","dominio","orden")
    list_filter = ("dominio",)
    search_fields = ("nombre",)

@admin.register(Foco)
class FocoAdmin(admin.ModelAdmin):
    list_display = ("id","nombre","estandar","orden")
    list_filter = ("estandar__dominio","estandar")
    search_fields = ("nombre",)

@admin.register(Descriptor)
class DescriptorAdmin(admin.ModelAdmin):
    list_display = ("id","foco","orden")
    list_filter = ("foco__estandar__dominio","foco__estandar","foco")
    search_fields = ("texto",)

class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0

@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ("id","nombre","version","activo","creado_en")
    inlines = [ChecklistItemInline]