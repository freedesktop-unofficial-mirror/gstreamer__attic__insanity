from web.insanity.models import TestRun, Test, TestClassInfo, TestCheckListList, TestArgumentsDict, TestExtraInfoDict
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
import time
from datetime import date

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
                    extras[x.conatinerid].append(x)

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
        "limit":limit
        })

def handler404(request):
    return "Something went wrong !"
