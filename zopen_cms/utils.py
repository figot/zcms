# -*- encoding: utf-8 -*-

from datetime import datetime
from docutils.core import publish_parts
from docutils.writers.html4css1 import Writer
from pyramid.url import resource_url
import urllib2
import os
import chardet
from string import Template
from pyramid.response import Response
from models import Folder, Document

_templates_cache = {}

def getDisplayTime(input_time, show_mode='localdate'):
    """ 人性化的时间显示: (支持时区转换)

    time 是datetime类型，或者timestampe的服点数，
    最后的show_mode是如下:

    - localdate: 直接转换为本地时间显示，到天
    - localdatetime: 直接转换为本地时间显示，到 年月日时分
    - localtime: 直接转换为本地时间显示，到 时分
    - deadline: 期限，和当前时间的比较天数差别，这个时候返回2个值的 ('late', '12天前')
    - humandate: 人可阅读的天，今天、明天、后天、昨天、前天，或者具体年月日 ('today', '今天')
    """
    if not input_time:
        return ''
    
    today = datetime.now()
    time_date = datetime(input_time.year, input_time.month, input_time.day)
    year, month, day = today.year, today.month, today.day
    today_start = datetime(year, month, day)

    to_date = today_start - time_date

    # 期限任务的期限
    if show_mode == 'localdate':
        return input_time.strftime('%Y-%m-%d')
    elif show_mode == 'localdatetime':
        return input_time.strftime('%Y-%m-%d %H:%M')
    elif show_mode == 'localtime':
        return input_time.strftime('%H:%M')
    elif show_mode == 'deadline':
        if to_date == 0:
            return ('Today', '今天')
        elif to_date < 0:
            if to_date == -1:
                return (None, '明天')
            elif to_date == -2:
                return (None, '后天')
            else:
                return (None, str(int(-to_date))+'天')
        elif to_date > 0:
            if to_date == 1:
                return ('late', '昨天')
            elif to_date == 2:
                return ('late', '前天')
            else:
                return ('late', str(int(to_date))+'天前')
    elif show_mode == 'humandate':
        if to_date == 0:
            return ('Today', '今天')
        elif to_date < 0:
            if to_date == -1:
                return (None, '明天')
            elif to_date == -2:
                return (None, '后天')
            else:
                return (None, input_time.strftime('%Y-%m-%d'))
        elif to_date > 0:
            if to_date == 1:
                return ('late', '昨天')
            elif to_date == 2:
                return ('late', '前天')
            else:
                return ('late', input_time.strftime('%Y-%m-%d'))

def rst2html(rst, path, context, request):
    settings = {
        'halt_level':6,
        'input_encoding':'UTF-8',
        'output_encoding':'UTF-8',
        'initial_header_level':2,
        'file_insertion_enabled':1,
        'raw_enabled':1,
        'writer_name':'html',
        'language_code':'zh_cn',
        'context':context,
        'request':request
    }

    # TODO(Prim): rst文本里面有border="1"?
    # 表格生成的时候，会出现一个border=1，需要去除
    rst = rst.replace('border="1"', '')

    return publish_parts(
        rst,
        source_path = path,
        writer = Writer(),
        settings_overrides = settings
    )['html_body']

def render_html(frs_file, request):
    data = frs_file.data

    lstrip_data = data.lstrip()
    # windows会自动增加utf8的标识字
    if lstrip_data[0:3]== '\xef\xbb\xbf':
        lstrip_data = lstrip_data[3:]

    # 判断文件内容是否为html
    # 文件内容不是html时，认为内容为rst文本
    if lstrip_data and lstrip_data[0] == '<':
        return data

    # 不显示的标题区域，标题在zpt里面独立处理了
    if lstrip_data.startswith('======'):
        splitted_data = lstrip_data.split('\n', 3)
        data = splitted_data[-1]
        # title = splitted_data[1]

    ospath = frs_file.ospath
    return rst2html(data, str(ospath), frs_file, request)

def get_site(context):
    while context.vpath.find('/', 1) != -1:
        context = context.__parent__
    return context

def render_tabs(site, context, request):
    if site is None:
        return ''

    html_list = []
    for tab in site.values(True, True):
        class_str = 'plain'
        if context.vpath.startswith(tab.vpath):
            class_str = "selected"

        tab_url = resource_url(tab, request)  # hack
        if tab_url.endswith('.rst/'):
            tab_url = tab_url[:-1]

        html_list.append(
            '<li id="nav-%s" class="%s"><a href="%s">%s</a></li>'
            % (tab.__name__, class_str, tab_url, tab.title)
        )

    html = '<ul id="portal-globalnav">%s</ul>' % ''.join(html_list)
    return html.decode('utf-8')

def rst_col_path(name, context):
    # 往上找左右列
    if context.__name__ == '':
        return '', ''
    source_path = str(context.ospath)
    if isinstance(context, Folder):
        source_path = os.path.join(source_path, 'asf.rst')
    dc_main = context.metadata
    col = dc_main.get(name, '')
    if col != '':
        return col, source_path
    if context.__parent__ is None:
        return col, source_path
    return rst_col_path(name, context.__parent__)


def render_cols(context, request):
    html_left = ''
    html_right = ''
    right_col_rst, right_col_path = rst_col_path('right_col', context)
    left_col_rst, left_col_path = rst_col_path('left_col', context)
    center_col_rst, center_col_path = rst_col_path('center_col', context)

    if left_col_rst == '':
        html_left = ''
    else:
        cvt_html = rst2html(left_col_rst, left_col_path, context, request)
        if cvt_html.startswith('<td') or cvt_html.lstrip().startswith('<td'):
            html_left = cvt_html
        else:
            html_left = """<td id="portal-column-one">
                <div class="visualPadding">%s</div></td>
                """ % rst2html(left_col_rst, left_col_path, context, request)

    if right_col_rst == '':
        html_right = ''
    else:
        cvt_html = rst2html(right_col_rst, right_col_path, context, request)
        if cvt_html.startswith('<td') or cvt_html.lstrip().startswith('<td'):
            html_right = cvt_html
        else:
            html_right = """<td id="portal-column-two">
                <div class="visualPadding">%s</div></td>
                """ % rst2html(right_col_rst, right_col_path, context, request)

    if center_col_rst == '':
        html_center = ''
    else:
        cvt_html = rst2html(center_col_rst, center_col_path, context, request)
        html_center = '<div>%s</div>' % rst2html(
            center_col_rst, center_col_path, context, request)

    html_cols = {
        'left': html_left,
        'right': html_right,
        'center': html_center
    }
    return html_cols

def render_content(context, request, content, **kw):
    # 获取模式，得到所有上级的属性


    site = get_site(context)

    site_title = site.title
    dc = context.metadata


    description = dc.get('description', '')
    doc_title = dc.get('title', context.__name__)
    site_title = doc_title + ' - ' + site_title

    # 渲染总标签栏目
    if context.vpath != '/':
        tabs = render_tabs(site, context, request)
    else:
        tabs = ''

    # 渲染左右列
    html_cols = render_cols(context, request)

    # 根据模版来渲染最终效果

    kw = dict(
        head='<title>%s</title>' % site_title,
        nav=tabs,
        left_col=html_cols.get('left', ''),
        right_col=html_cols.get('right', ''),
        content=content,
        description=description
    )

    # 线上运行，多站点支持, support ngix
    path_info = request.environ['PATH_INFO'].split('/', 2)
    if len(path_info) > 2:
        request.environ['HTTP_X_VHM_ROOT'] = '/' + site.__name__
        request.environ['PATH_INFO'] = '/%s' % path_info[2]

    theme = site.metadata.get('theme_url', 'http://localhost:6543/themes/bootstrap/index.html')
    template = get_theme_template(theme)
    output = template.substitute(kw).encode('utf8')
    return Response(output, headerlist=[
                ('Content-length', str(len(output))),
                ('Content-type', 'text/html; charset=UTF-8')
	    ])

def get_theme_template(theme_url):
    # cache template, TODO refresh cache
    global _templates_cache
    if theme_url in _templates_cache:
        return _templates_cache[theme_url]

    theme = urllib2.urlopen(theme_url).read()
    text_encoding = chardet.detect(theme)['encoding']
    theme = theme.decode(text_encoding)
    template = Template(theme)
    _templates_cache[theme_url] = template
    return template