class AppointmentError(Exception):
    pass


class SlotUnavailableError(AppointmentError):
    pass


class InvalidSlotError(AppointmentError):
    pass


class AppointmentStatusError(AppointmentError):
    pass
