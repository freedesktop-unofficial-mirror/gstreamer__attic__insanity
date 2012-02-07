import os.path
import math
from django import template
from django.utils.html import escape

register = template.Library()

@register.tag
def test_arg_value(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        func, arg_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly one arguments" % token.contents.split()[0]

    return TestArgValueNode(arg_name)

@register.simple_tag
def verticalize(toparse):
    return "<br>".join([a[0].capitalize() for a in toparse.split('-')])

@register.simple_tag
def split_dash_lines(toparse):
    return "<br>".join([a.capitalize() for a in toparse.split('-')])

@register.tag
def test_extrainfo_value(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        func, value_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly one arguments" % token.contents.split()[0]

    return TestExtraInfoValueNode(value_name)

# common methods
def escape_val(val, safe=False):
    if isinstance(val, list) or isinstance(val, tuple):
        res = ["<ul>"]
        for item in val:
            res.extend(["<li>", escape_val(item, safe), "</li>"])
        res.append("</ul>")
        return "".join(res)
    if isinstance(val, dict):
        res = ["<dl>"]
        for k,v in val.iteritems():
            res.extend(["<dt>", escape_val(k, safe), "</dt>"])
            res.extend(["<dd>", escape_val(v, safe), "</dd>"])
        res.append("</dl>")
        return "".join(res)
    if safe:
        return unicode(val)
    return escape(unicode(val))


def time_to_string(value):
    if value == -1.0:
        return "--:--:--.---"
    ms = value / 1000000
    sec = ms / 1000
    ms = ms % 1000
    mins = sec / 60
    sec = sec % 60
    hours = mins / 60
    return "%02d:%02d:%02d.%03d" % (hours, mins, sec, ms)

class TestArgValueNode(template.Node):

    def __init__(self, arg):
        self._arg_name = arg

    def render(self, context):
        mstypes = ["media-start",
                   "media-duration",
                   "start",
                   "duration"]
        # render based on the type
        arg = context[self._arg_name]
        res = None
        try:
            if arg.name.name in mstypes:
                res = time_to_string(arg.value * 1000000)
            else:
                res = escape_val(arg.value)
        finally:
            return res

class TestExtraInfoValueNode(template.Node):

    def __init__(self, extrainfo):
        self._extrainfo_name = extrainfo

    def render(self, context):
        mstypes = ["test-total-duration",
                   "test-setup-duration",
                   "remote-instance-creation-delay",
                   "subprocess-spawn-time",
                   "first-buffer-timestamp",
                   "total-uri-duration"]


        def elements_used_dict(elements):
            # returns a dictionnary of the tree of elements used
            def insert_in_dict(d,el,par,klass):
                if d == {}:
                    d[el] = [klass, {}]
                    return True
                for k in d.iterkeys():
                    if k == par:
                        d[k][1][el] = [klass, {}]
                        return True
                    if d[k][1] != {}:
                        if insert_in_dict(d[k][1], el, par, klass):
                            return True
                return False
            def switch_dict(d):
                res = {}
                for k,v in d.iteritems():
                    klass, childs = v
                    res["<b>%s</b> (type:%s)" % (k, klass)] = switch_dict(childs)
                return res
            d = {}
            for el, klass, container in elements:
                insert_in_dict(d, el, container, klass)

            return switch_dict(d)

        # render based on the type
        extrainfo = context[self._extrainfo_name]
        # insert custom extrainfo value handling here
        res = None
        try:
            if extrainfo.name.name in mstypes:
                # values are stored in milliseconds, we bring them back to ns
                res = time_to_string(extrainfo.value * 1000000)
            elif extrainfo.name.name.endswith(".duration"):
                res = time_to_string(extrainfo.value * 1000000)
            else:
                res = escape_val(extrainfo.value)
        finally:
            return res

@register.inclusion_tag('insanityweb/test_args_dict.html')
def test_args_dict(test, fullarguments=None):
    args = test.arguments.all().select_related(depth=1)
    return {'args':args}


@register.inclusion_tag('insanityweb/test_checklist_dict.html')
def test_checklist_dict(test, fullchecklist=None):
    explanations = {}
    for e in test.error_explanations.all().select_related(depth=1):
        explanations[e.name.id] = e.txtvalue

    results = []
    for r in test.checklist.all().select_related(depth=1):
        r.explanation = explanations.get(r.name.id, None)
        results.append(r)

    return {'results': results}

@register.inclusion_tag('insanityweb/test_extrainfo_dict.html')
def test_extrainfo_dict(test):
    extrainfos = test.extrainfo.all().select_related(depth=1)
    return {'extrainfos':extrainfos}

@register.inclusion_tag('insanityweb/matrix_checklist_row.html')
def matrix_checklist_row(test, fullchecklist, fullarguments,
                         allchecks, allargs, allextrainfo):
    args = test._get_full_arguments(fullarguments, allargs.get(test, []))
    checks = allchecks.get(test, [])
    test_error = test._test_error(allextras=allextrainfo.get(test, []))
    return {'test':test,
            'arguments':args,
            'results':checks,
            'test_error':test_error}

@register.inclusion_tag('insanityweb/matrix_navigation.html', takes_context=True)
def matrix_navigation(context, adjacent_pages=2):
    testrun = context['testrun']
    currentoffset = context.get('offset', 0)
    limit = context.get('limit', 100)
    onlyfailed = context.get('onlyfailed', 0)
    showscenario = context.get('showscenario', 1)
    crashonly = context.get('crashonly', 0)
    timedoutonly = context.get('timedoutonly', 0)
    totalnb = context["totalnb"]

    # This creates a navigation <div> for the given page
    # for the time being we just calculate the offset for the
    # previous and next series
    totalpages = int(math.ceil(float(totalnb) / limit))
    pages = []
    for i in range(totalpages):
        d = {}
        d["index"] = i
        d["iscurrent"] = (currentoffset == limit * i)
        d["offset"] = limit * i
        pages.append(d)
    if len(pages) == 1:
        # Everything fits on one page, no pagination needed:
        pages = []

    poff = currentoffset - limit
    noff = currentoffset + limit
    return {'testrun':testrun,
            'prevoffset':poff,
            'limit':limit,
            'currentoffset':currentoffset,
            'nextoffset':noff,
            'onlyfailed':onlyfailed,
            'showscenario':showscenario,
            'crashonly':crashonly,
            'timedoutonly':timedoutonly,
            'pages':pages
            }
