"""Gallery views — ألبومات وقائمة مع lightbox."""
from django.shortcuts import get_object_or_404, render

from .models import GalleryAlbum


def album_list(request):
    albums = GalleryAlbum.objects.prefetch_related("items")
    return render(request, "gallery/list.html", {"albums": albums})


def album_detail(request, slug):
    album = get_object_or_404(GalleryAlbum.objects.prefetch_related("items"), slug=slug)
    return render(request, "gallery/detail.html", {"album": album, "meta_description": album.description or album.title_ar})
