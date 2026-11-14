"""
Manage console — شاشات مsimplified داخلية للموظفين بدل Django admin.
يشتغل على صلاحيات Django نفسها (view/add/change/delete لكل موديل).
الوصول: staff فقط (is_staff). لا شيء يظهر لغير الموظفين.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db import models as dj_models
from django.db.models import Q
from django.forms import ModelForm
from django.http import HttpRequest, HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.core.manage import ManageCfg, model_cfg, model_for, perms_for, grouped_manageable_for


def _staff(user) -> bool:
    return user.is_authenticated and user.is_staff


def _cfg_or_404(app_label: str, model_name: str) -> ManageCfg:
    cfg = model_cfg(app_label, model_name.lower())
    if cfg is None:
        raise Http404("unknown managed model")
    return cfg


def _field_label(field) -> str:
    return str(field.verbose_name or field.name)


def _build_form(model, cfg: ManageCfg, instance=None) -> type[ModelForm]:
    widgets = {}
    for f in model._meta.get_fields():
        if not hasattr(f, "name") or not hasattr(f, "serialize"):
            continue
        name = f.name
        internal = f.get_internal_type()
        if internal == "DateTimeField":
            widgets[name] = forms.DateTimeInput(attrs={"type": "datetime-local", "class": "input", "step": "60"}, format="%Y-%m-%dT%H:%M")
        elif internal == "DateField":
            widgets[name] = forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d")
        elif internal == "TimeField":
            widgets[name] = forms.TimeInput(attrs={"type": "time", "class": "input"}, format="%H:%M")
        elif internal in ("DecimalField", "FloatField"):
            widgets[name] = forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": "0", "inputmode": "decimal"})
        elif internal == "TextField":
            widgets[name] = forms.Textarea(attrs={"class": "input", "rows": 4})
        elif internal in ("FileField", "ImageField"):
            widgets[name] = forms.ClearableFileInput(attrs={"class": "input"})
        elif internal == "BooleanField":
            widgets[name] = forms.CheckboxInput(attrs={"class": "accent-[var(--brand-navy)] w-5 h-5 align-middle ms-2"})
        elif getattr(f, "choices", None):
            widgets[name] = forms.Select(attrs={"class": "input"})
        elif f.is_relation:
            widgets[name] = forms.Select(attrs={"class": "input"})
        else:
            widgets[name] = forms.TextInput(attrs={"class": "input"})

    for _name, _widget in widgets.items():
        if isinstance(_widget, forms.DateTimeInput):
            _widget.input_formats = ["%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"]
        elif isinstance(_widget, forms.DateInput):
            _widget.input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        elif isinstance(_widget, forms.TimeInput):
            _widget.input_formats = ["%H:%M", "%H:%M:%S"]

    fields = [
        f.name for f in model._meta.fields
        if f.name not in cfg.exclude_fields and f.name not in cfg.readonly_fields
        and getattr(f, "editable", True) and getattr(f, "serialize", True)
    ]

    Meta = type("Meta", (), {"model": model, "fields": fields, "widgets": widgets})
    return type("ManageForm", (ModelForm,), {"Meta": Meta})


def _display_value(obj, col: str):
    cur = obj
    parts = col.split(".")
    # support get_FIELD_display automatically for single-field choice columns
    if len(parts) == 1:
        getter = getattr(obj, f"get_{col}_display", None)
        if callable(getter):
            try:
                return str(getter())
            except Exception:
                pass
    for part in parts:
        cur = getattr(cur, part, None)
        if callable(cur):
            try:
                cur = cur()
            except Exception:
                return ""
        if cur is None:
            return "—"
    import datetime as _dt
    if isinstance(cur, _dt.datetime):
        return cur.strftime("%d/%m/%Y %H:%M")
    if isinstance(cur, _dt.date):
        return cur.strftime("%d/%m/%Y")
    if cur is True:
        return "✓"
    if cur is False:
        return "—"
    return str(cur)


def _apply_search(qs, model, cfg: ManageCfg, q: str):
    if not q or not cfg.search_fields:
        return qs
    cond = Q()
    for field in cfg.search_fields:
        if "__" in field or field in ("reference",):
            cond |= Q(**{field + "__icontains": q})
        else:
            cond |= Q(**{field + "__icontains": q})
    return qs.filter(cond)


def _apply_filters(qs, model, cfg: ManageCfg, params):
    for field in cfg.list_filter:
        value = params.get(field)
        if value in (None, ""):
            continue
        f = model._meta.get_field(field)
        if f.get_internal_type() == "BooleanField":
            qs = qs.filter(**{field: value in ("1", "true", "True")})
        elif value.isdigit():
            qs = qs.filter(**{field: int(value)})
        else:
            qs = qs.filter(**{field: value})
    return qs


@user_passes_test(_staff, login_url="accounts:login")
def manage_index(request: HttpRequest) -> HttpResponse:
    groups = grouped_manageable_for(request.user)
    return render(request, "manage/index.html", {
        "groups": groups,
        "breadcrumbs": [_("لوحة التحكم"), _("القوائم الإدارية")],
    })


@user_passes_test(_staff, login_url="accounts:login")
def manage_list(request: HttpRequest, app_label: str, model_name: str) -> HttpResponse:
    cfg = _cfg_or_404(app_label, model_name)
    model = model_for(cfg)
    perms = perms_for(request.user, cfg)
    if not any(perms.values()):
        return HttpResponseForbidden(_("مفيش صلاحية"))

    qs = model.objects.all()
    qs = _apply_search(qs, model, cfg, (request.GET.get("q") or "").strip())
    qs = _apply_filters(qs, model, cfg, request.GET)
    try:
        qs = qs.order_by(*(cfg.ordering or ("-pk",)))
    except Exception:
        qs = qs.order_by("-pk")

    page = Paginator(qs, 20).get_page(request.GET.get("page") or 1)
    columns = []
    for col in cfg.list_display:
        label = col
        try:
            f = model._meta.get_field(col)
        except Exception:
            f = None
        label = _field_label(f) if f is not None else col
        columns.append({"key": col, "label": label})

    rows = [
        {"pk": obj.pk, "cells": [_display_value(obj, c) for c in cfg.list_display]}
        for obj in page.object_list
    ]

    # filter UI
    filter_fields = []
    for field in cfg.list_filter:
        f = model._meta.get_field(field)
        label = _field_label(f)
        options = None
        if f.choices:
            options = list(f.choices)
        elif f.get_internal_type() == "BooleanField":
            options = [("1", _("نعم")), ("0", _("لا"))]
        filter_fields.append({
            "name": field, "label": label, "options": options,
            "value": request.GET.get(field, ""),
        })

    return render(request, "manage/list.html", {
        "cfg": cfg, "perms": perms, "model": model,
        "count": qs.count(),
        "page_obj": page,
        "paginator": page.paginator,
        "columns": columns, "rows": rows,
        "filter_fields": filter_fields,
        "q": (request.GET.get("q") or ""),
        "has_add": perms["add"], "has_change": perms["change"], "has_delete": perms["delete"],
        "verbose_name": str(model._meta.verbose_name),
        "verbose_name_plural": str(model._meta.verbose_name_plural),
        "breadcrumbs": [_("لوحة التحكم"), _("القوائم الإدارية"), str(model._meta.verbose_name_plural)],
    })


@user_passes_test(_staff, login_url="accounts:login")
def manage_create(request: HttpRequest, app_label: str, model_name: str) -> HttpResponse:
    cfg = _cfg_or_404(app_label, model_name)
    model = model_for(cfg)
    perms = perms_for(request.user, cfg)
    if not perms["add"]:
        return HttpResponseForbidden(_("مفيش صلاحية"))

    Form = _build_form(model, cfg)
    form = Form(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, "created_by_id") and obj.created_by_id is None:
            obj.created_by = request.user
        obj.save()
        messages.success(request, _("تم الحفظ بنجاح"))
        return redirect(reverse("core:manage_list", kwargs={"app_label": cfg.app_label, "model_name": cfg.model_name}))

    field_list = [(bound, isinstance(bound.field.widget, forms.CheckboxInput)) for bound in form]
    return render(request, "manage/form.html", {
        "cfg": cfg, "form": form, "field_list": field_list, "model": model, "is_edit": False,
        "title": _("إضافة") + " " + str(model._meta.verbose_name),
        "verbose_name_plural": str(model._meta.verbose_name_plural),
        "breadcrumbs": [_("لوحة التحكم"), _("القوائم الإدارية"), str(model._meta.verbose_name_plural)],
    })


@user_passes_test(_staff, login_url="accounts:login")
def manage_edit(request: HttpRequest, app_label: str, model_name: str, pk: int) -> HttpResponse:
    cfg = _cfg_or_404(app_label, model_name)
    model = model_for(cfg)
    perms = perms_for(request.user, cfg)
    if not perms["change"]:
        return HttpResponseForbidden(_("مفيش صلاحية"))

    obj = get_object_or_404(model, pk=pk)
    Form = _build_form(model, cfg, instance=obj)
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("تم الحفظ بنجاح"))
        return redirect(reverse("core:manage_list", kwargs={"app_label": cfg.app_label, "model_name": cfg.model_name}))

    field_list = [(bound, isinstance(bound.field.widget, forms.CheckboxInput)) for bound in form]
    return render(request, "manage/form.html", {
        "cfg": cfg, "form": form, "field_list": field_list, "model": model, "is_edit": True, "obj": obj,
        "title": _("تعديل") + " " + str(model._meta.verbose_name),
        "verbose_name_plural": str(model._meta.verbose_name_plural),
        "breadcrumbs": [_("لوحة التحكم"), _("القوائم الإدارية"), str(model._meta.verbose_name_plural)],
    })


@user_passes_test(_staff, login_url="accounts:login")
def manage_delete(request: HttpRequest, app_label: str, model_name: str, pk: int) -> HttpResponse:
    cfg = _cfg_or_404(app_label, model_name)
    model = model_for(cfg)
    perms = perms_for(request.user, cfg)
    if not perms["delete"]:
        return HttpResponseForbidden(_("مفيش صلاحية للحذف"))

    obj = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        label = str(obj)
        try:
            obj.delete()
            messages.success(request, _("تم الحذف: %(n)s") % {"n": label})
        except Exception as exc:
            messages.error(request, _("تعذر الحذف — قد تكون مرتبطة ببيانات تانية: %(e)s") % {"e": exc})
        return redirect(reverse("core:manage_list", kwargs={"app_label": cfg.app_label, "model_name": cfg.model_name}))

    return render(request, "manage/delete.html", {
        "cfg": cfg, "obj": obj, "model": model,
        "list_url": reverse("core:manage_list", kwargs={"app_label": cfg.app_label, "model_name": cfg.model_name}),
        "title": _("حذف") + " " + str(model._meta.verbose_name),
        "breadcrumbs": [_("لوحة التحكم"), _("القوائم الإدارية"), str(model._meta.verbose_name_plural)],
    })
