# -*- coding: utf-8 -*-
import functools
import json
import os
import re

import django
from django.conf import settings
from django.contrib.admindocs.views import simplify_regex
from django.core.exceptions import ViewDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
import django.contrib.admin.options

from django_extensions.management.color import color_style, no_style
from django_extensions.management.utils import signalcommand

if django.VERSION >= (2, 0):
    from django.urls import URLPattern, URLResolver  # type: ignore


    class RegexURLPattern:  # type: ignore
        pass


    class RegexURLResolver:  # type: ignore
        pass


    class LocaleRegexURLResolver:  # type: ignore
        pass


    def describe_pattern(p):
        return str(p.pattern)
else:
    try:
        from django.urls import RegexURLPattern, RegexURLResolver, LocaleRegexURLResolver  # type: ignore
    except ImportError:
        from django.core.urlresolvers import RegexURLPattern, RegexURLResolver, LocaleRegexURLResolver  # type: ignore


    class URLPattern:  # type: ignore
        pass


    class URLResolver:  # type: ignore
        pass


    def describe_pattern(p):
        return p.regex.pattern

FMTR = {
    'dense': "{url}\t{module}\t{url_name}\t{decorator}",
    'table': "{url},{module},{url_name},{decorator}",
    'aligned': "{url},{module},{url_name},{decorator}",
    'verbose': "{url}\n\tController: {module}\n\tURL Name: {url_name}\n\tDecorators: {decorator}\n",
    'json': '',
    'pretty-json': ''
}


class Command(BaseCommand):
    help = "导出api接口文档"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--output", "-o", dest="unsorted",
            help="输出文档路径"
        )
        parser.add_argument(
            "--app", "-a", action="append", dest="app",
            help="选择app"
        )

    @signalcommand
    def handle(self, *args, **options):
        settings_modules = [settings]
        output = options.get('output', 'output.md')
        self.app = options.get('app', None)
        urlconf = 'ROOT_URLCONF'

        views = []
        for settings_mod in settings_modules:
            if not hasattr(settings_mod, urlconf):
                raise CommandError("Settings module {} does not have the attribute {}.".format(settings_mod, urlconf))
            try:
                urlconf = __import__(getattr(settings_mod, urlconf), {}, {}, [''])
            except Exception as e:
                if options['traceback']:
                    import traceback
                    traceback.print_exc()
                continue

            view_functions = self.extract_views_from_urlpatterns(urlconf.urlpatterns)
            for (func, regex, url_name) in view_functions:
                if hasattr(func, '__name__'):
                    func_name = func.__name__
                elif hasattr(func, '__class__'):
                    func_name = '%s()' % func.__class__.__name__
                else:
                    func_name = re.sub(r' at 0x[0-9a-f]+', '', repr(func))

                module = '{0}.{1}'.format(func.__module__, func_name)
                app_name = module.split('.')[0]
                if self.app and app_name not in self.app:
                    continue
                url_name = url_name or ''
                url = simplify_regex(regex)
                views.append((url, func, url_name))

        docs = []
        for url, func, url_name in views:
            try:
                if hasattr(func, 'cls') and url_name:
                    func_name = url_name.split('-')[1]
                    if hasattr(func.cls, func_name):
                        f = getattr(func.cls, func_name)
                        doc_domain = self.generate_doc(f, url, func_name)
                        if doc_domain:
                            docs.extend(doc_domain)
                            docs.extend(['', '', ''])  # 空3行
            except Exception as e:
                print(e)
        # 保存文件
        self.save_doc(docs, output)

    def extract_views_from_urlpatterns(self, urlpatterns, base='', namespace=None):
        """
        Return a list of views from a list of urlpatterns.

        Each object in the returned list is a three-tuple: (view_func, regex, name)
        """
        views = []
        for p in urlpatterns:
            if isinstance(p, (URLPattern, RegexURLPattern)):
                try:
                    if not p.name:
                        name = p.name
                    elif namespace:
                        name = '{0}:{1}'.format(namespace, p.name)
                    else:
                        name = p.name
                    pattern = describe_pattern(p)
                    views.append((p.callback, base + pattern, name))
                except ViewDoesNotExist:
                    continue
            elif isinstance(p, (URLResolver, RegexURLResolver)):
                try:
                    # if self.app:  # 筛选app
                    #     app_name = p.app_name
                    #     if app_name not in self.app:
                    #         continue
                    patterns = p.url_patterns
                except ImportError:
                    continue
                if namespace and p.namespace:
                    _namespace = '{0}:{1}'.format(namespace, p.namespace)
                else:
                    _namespace = (p.namespace or namespace)
                pattern = describe_pattern(p)
                # if isinstance(p, LocaleRegexURLResolver):
                #     for langauge in self.LANGUAGES:
                #         with translation.override(langauge[0]):
                #             views.extend(
                #                 self.extract_views_from_urlpatterns(patterns, base + pattern, namespace=_namespace))
                # else:
                views.extend(self.extract_views_from_urlpatterns(patterns, base + pattern, namespace=_namespace))
            elif hasattr(p, '_get_callback'):
                try:
                    views.append((p._get_callback(), base + describe_pattern(p), p.name))
                except ViewDoesNotExist:
                    continue
            elif hasattr(p, 'url_patterns') or hasattr(p, '_get_url_patterns'):
                try:
                    patterns = p.url_patterns
                except ImportError:
                    continue
                views.extend(
                    self.extract_views_from_urlpatterns(patterns, base + describe_pattern(p), namespace=namespace))
            else:
                raise TypeError("%s does not appear to be a urlpattern object" % p)
        return views

    def generate_doc(self, func, url, func_name):
        TEMPLATE = [
            '## %(name)s',
            '### **[%(method)s] %(url)s**',
            '### **参数:**',
            '| 请求参数      |     参数类型 |   参数说明   |',
            '| :--------    | :--------    | :------     |',
            '%(request_params)s',
            '### **返回参数**',
            '| 返回参数      |     参数类型 |   参数说明   |',
            '| :--------    | :--------    | :------     |',
            '%(response_params)s',
            '### **返回示例**',
            '```',
            '%(example)s',
            '```',
        ]
        doc = func.__doc__
        # TODO
        kwargs = self.extract_func_doc(doc)
        if kwargs:
            if func_name == 'list':
                method = 'GET'
            elif func_name == 'create':
                method = 'POST'
            else:
                method = ' '.join(func.bind_to_methods)

            name, request_params, response_params, example = kwargs
            request_params = self.extract_params(request_params)
            response_params = self.extract_params(response_params)

            doc_domain = list()
            doc_domain.append(TEMPLATE[0] % {'name': name})
            doc_domain.append(TEMPLATE[1] % {'method': method, 'url': url})
            doc_domain.extend(TEMPLATE[3:5])
            doc_domain.extend(request_params)
            doc_domain.extend(TEMPLATE[6:9])
            doc_domain.extend(response_params)
            doc_domain.extend(TEMPLATE[10:12])
            doc_domain.extend(example)
            doc_domain.append(TEMPLATE[-1])
            return doc_domain
        else:
            return False

    def extract_params(self, params):
        results = []
        PARAM_TEMPLATE = '| %(param_name)s | %(param_type)s | %(param)s |'
        try:
            for param in params:
                params_splited = param.split(':')
                param_name = params_splited[0]
                param_values_splited = params_splited[1].split(',')
                param_type = param_values_splited[0]
                param = ''.join(param_values_splited[1:])
                results.append(PARAM_TEMPLATE % {'param_name': param_name, 'param_type': param_type, 'param': param})
        except Exception as e:
            pass
        return results

    def extract_func_doc(self, doc):
        try:
            lines = [i.strip() for i in doc.split('\n')]
            name = lines[0]

            index_args = lines.index('Args:')
            index_return = lines.index('Return:')
            index_example = lines.index('Example:')

            request_params = lines[index_args + 1:index_return]
            response_params = lines[index_return + 1:index_example]
            # example = '\n'.join(lines[index_example + 1:])
            example = lines[index_example + 1:]

            return (name, request_params, response_params, example)
        except Exception as e:
            # print(e)
            return False

    def save_doc(self, docs, output):
        # 保存文件
        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
            os.mkdir(output_dir)
        with open(output, 'w') as f:
            for doc_line in docs:
                f.write('%s \n' % doc_line)
        self.stdout.write('完成: %s' % output)
