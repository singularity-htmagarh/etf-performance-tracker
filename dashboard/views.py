from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from dashboard.services import PERIODS, REGIONS, build_dashboard_context
from warehouse.ingest import run_ingestion


def index(request):
    context = build_dashboard_context(request.GET)
    if request.GET.get("download") == "csv" and context.get("has_data"):
        response = HttpResponse(context["table_csv"], content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="etf_performance_{date.today().isoformat()}.csv"'
        return response
    return render(request, "dashboard/index.html", context)


@require_POST
def sync(request):
    regions = [region for region in request.POST.getlist("region") if region in REGIONS]
    if not regions:
        regions = list(REGIONS)
    period = request.POST.get("period")
    if period not in PERIODS:
        period = "3y"

    for region in regions:
        summary = run_ingestion(region, period=period)
        if summary["status"] == "failed":
            messages.error(request, f"{region} sync failed: {summary['note']}")
        else:
            messages.success(
                request,
                f"{region}: {summary['tickers_loaded']}/{summary['tickers_requested']} ETFs synced.",
            )

    from django.core.cache import cache

    cache.clear()
    query = request.POST.get("return_query", "")
    return redirect(f"{reverse('dashboard:index')}{'?' + query if query else ''}")