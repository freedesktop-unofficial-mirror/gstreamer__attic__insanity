from web.insanityweb.models import TestRun, Test, TestClassInfo, TestCheckListList, TestArgumentsDict, TestExtraInfoDict
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.http import HttpResponse
from django.conf import settings
import time
from datetime import date

from insanityweb.runner import get_runner

from functools import wraps
from django.http import HttpResponse
from django.utils import simplejson as json

def index(request):
    nbruns = request.GET.get("nbruns", 20)
    latest_runs = TestRun.objects.withcounts().order_by("-starttime")[:int(nbruns)]
    return render_to_response("insanityweb/index.html", {"latest_runs":latest_runs,
                                                      "nbruns":nbruns})

def testrun_summary(request, testrun_id):
    toplevel_only = bool(int(request.GET.get("toplevel",True)))
    tr = get_object_or_404(TestRun, pk=testrun_id)
    return render_to_response('insanityweb/testrun_summary.html',
                              {'testrun': tr,
                               'toplevel_only': toplevel_only})

def test_summary(request, test_id):
    tr = get_object_or_404(Test, pk=test_id)
    return render_to_response('insanityweb/test_summary.html', {'test': tr})

def available_tests(request):
    """ Returns a tree of all available tests """
    classinfos = TestClassInfo.objects.all()
    return render_to_response('insanityweb/available_tests.html',
                              {"classinfos": classinfos})

def matrix_view(request, testrun_id):
    tr = get_object_or_404(TestRun, pk=testrun_id)

    onlyfailed = bool(int(request.GET.get("onlyfailed",False)))
    showscenario = bool(int(request.GET.get("showscenario",True)))
    crashonly = bool(int(request.GET.get("crashonly", False)))
    timedoutonly = bool(int(request.GET.get("timedoutonly", False)))
    limit = int(request.GET.get("limit", 100))
    offset = int(request.GET.get("offset", 0))

    # let's get the test instances ...
    testsinst = Test.objects.nomonitors().select_related("type", "parentid", "checklist").filter(testrunid=tr)

    # and filter them according to the given parameters
    if onlyfailed:
        testsinst = testsinst.exclude(resultpercentage=100.0)

    # crashonly and timedoutonly are exclusive
    if crashonly:
        testsinst = testsinst.filter(checklist__name__name="subprocess-exited-normally",
                                     checklist__value=0)
    elif timedoutonly:
        testsinst = testsinst.filter(checklist__name__name="no-timeout",
                                     checklist__value=0)

    if not showscenario:
        sctypes = TestClassInfo.objects.scenarios()
        testsinst = testsinst.exclude(type__in=sctypes)

    tests = []
    # total number of potential results for this query
    # FIXME : This should be cached
    totalnb = testsinst.count()
    res = list(testsinst[offset:offset+limit])

    error_summary = {}
    for t in res:
        for r in t.checklist.all().select_related(depth=1):
            if r.failure:
                if r.name.id not in error_summary:
                    error_summary[r.name.id] = {
                        'name': r.name.name,
                        'description': r.name.description,
                        'count': 0
                    }
                error_summary[r.name.id]['count'] += 1

    error_summary = error_summary.values()
    error_summary.sort(key=lambda x: x['count'], reverse=True)

    if totalnb != 0 and res != []:
        v = Test.objects.values_list("type",flat=True).filter(id__in=(x.id for x in res)).distinct()

        # get the TestClassInfo for the available tests
        testtypes = TestClassInfo.objects.select_related(depth=1).filter(id__in=v)

        for t in testtypes:
            query = [x for x in res if x.type == t]

            # skip empty sets early
            if len(query) == 0:
                continue

            # return dictionnaries of:
            # key : test
            # value : list of args/checks/extrainfos
            checks = {}
            for x in TestCheckListList.objects.select_related("containerid__type","name","value").filter(containerid__in=query).order_by("name"):
                if not x.containerid in checks.keys():
                    checks[x.containerid] = [x]
                else:
                    checks[x.containerid].append(x)

            args = {}
            for x in TestArgumentsDict.objects.select_related("containerid__type", "name","intvalue","txtvalue","blobvalue").filter(containerid__in=query).order_by("name"):
                if not x.containerid in args.keys():
                    args[x.containerid] = [x]
                else:
                    args[x.containerid].append(x)

            extras = {}
            for x in TestExtraInfoDict.objects.select_related("containerid__type", "name__name", "intvalue", "txtvalue", "blobvalue").filter(containerid__in=query,
                                                                                                                                       name__name__in=["subprocess-return-code","errors"]):
                if not x.containerid in extras.keys():
                    extras[x.containerid] = [x]
                else:
                    extras[x.containerid].append(x)

            tests.append({"type":t,
                          "tests":query,
                          "fullchecklist":t.fullchecklist,
                          "fullarguments":t.fullarguments,
                          "allchecks":checks,
                          "allargs":args,
                          "allextras":extras})

    return render_to_response('insanityweb/matrix_view.html',
                              {
        'testrun':tr,
        'sortedtests':tests,
        "totalnb":totalnb,
        'onlyfailed':int(onlyfailed),
        'showscenario':int(showscenario),
        'crashonly':int(crashonly),
        'timedoutonly':int(timedoutonly),
        "offset":offset,
        "limit":limit,
        'errorsummary': error_summary
        })

def handler404(request):
    return "Something went wrong !"

def render_to_json(**jsonargs):
    """
    Renders a JSON response with a given returned instance. Assumes json.dumps() can
    handle the result. The default output uses an indent of 4.

    @render_to_json()
    def a_view(request, arg1, argN):
        ...
        return {'x': range(4)}

    @render_to_json(indent=2)
    def a_view2(request):
        ...
        return [1, 2, 3]

    """
    def outer(f):
        @wraps(f)
        def inner_json(request, *args, **kwargs):
            result = f(request, *args, **kwargs)
            r = HttpResponse(mimetype='application/json')
            if result:
                indent = jsonargs.pop('indent', 4)
                r.write(json.dumps(result, indent=indent, **jsonargs))
            else:
                r.write("{}")
            return r
        return inner_json
    return outer

@render_to_json()
def current_progress(request):
    return {
        'progress': get_runner().get_progress()
    }

def current(request):
    runner = get_runner()
    test_names = runner.get_test_names()
    test_folders = settings.INSANITY_TEST_FOLDERS.items()

    if 'submit' in request.POST:
        test = request.POST.get('test', '')
        folder = request.POST.get('folder', '')
        if test in test_names and folder in settings.INSANITY_TEST_FOLDERS:
            runner.start_test(test, folder,
                settings.INSANITY_TEST_FOLDERS[folder].get('extra-arguments', {}))
        return redirect('web.insanityweb.views.current')

    progress = runner.get_progress()
    tests_running = (progress is not None)
    test = runner.get_test_name()
    folder = settings.INSANITY_TEST_FOLDERS.get(runner.get_test_folder(), {'name':'(unknown folder)'})['name']
    return render_to_response("insanityweb/current.html", locals())

def stop_current(request):
    if 'submit' in request.POST:
        get_runner().stop_test()
    return redirect('web.insanityweb.views.current')
