from .models import Announcement


def announcement(request):
    return {"announcement": Announcement.current()}
