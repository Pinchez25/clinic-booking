from rest_framework.routers import DefaultRouter

from appointments.views import AppointmentViewSet, PatientViewSet

router = DefaultRouter()
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("patients", PatientViewSet, basename="patient")

urlpatterns = router.urls
