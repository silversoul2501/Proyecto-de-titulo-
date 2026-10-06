from django.urls import path
from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("nueva/", views.evaluacion_nueva, name="nueva"),
    path("<int:pk>/", views.evaluacion_editar, name="editar"),
    path("<int:pk>/respuesta/<int:descriptor_id>/", views.respuesta_guardar, name="respuesta_guardar"),
    path("<int:pk>/respuesta/<int:respuesta_id>/evidencia/subir/", views.evidencia_subir, name="evidencia_subir"),
    path("evidencia/<int:eid>/borrar/", views.evidencia_borrar, name="evidencia_borrar"),
    path("<int:pk>/finalizar/", views.evaluacion_finalizar, name="finalizar"),
    path("<int:pk>/reabrir/", views.evaluacion_reabrir, name="reabrir"),
    path("<int:pk>/actualizar-meta/", views.evaluacion_actualizar_meta, name="actualizar_meta"),
    path("<int:pk>/resumen/", views.evaluacion_resumen, name="resumen"),
    path("<int:pk>/pdf/", views.evaluacion_pdf, name="pdf"),
    path("", views.evaluacion_lista, name="lista"),
]