from html.parser import HTMLParser
import os
import codecs
from typing import Tuple


class Converter(HTMLParser):
    md_file: str
    temp_tag: str
    code_box: bool
    div_count: int
    code_box_div_num: int
    ol_count: int
    related_data: list
    is_link: bool
    link_ref: str
    ignore_data: bool
    class_div_count: int
    ignore_div: bool
    table_start: Tuple[int, int]

    def __init__(self):
        super().__init__()
        self.md_file = ''
        self.code_box = False
        self.div_count = 0
        self.code_box_div_num = 0
        self.ol_count = 0
        self.temp_tag = ''
        self.related_data = []
        self.is_link = False
        self.link_ref = ''
        self.ignore_data = False
        self.class_div_count = 0
        self.ignore_div = False

    def handle_starttag(self, tag, attrs):
        if self.ignore_data:
            return None
        elif tag == 'br':
            self.md_file += '  \n'
        elif tag == 'hr':
            self.md_file += '\n***  \n'
        elif tag == 'title':
            self.md_file += '# '
        elif tag == 'h1':
            self.md_file += '# '
        elif tag == 'h2':
            self.md_file += '## '
        elif tag == 'h3':
            self.md_file += '### '
        elif tag == 'b' or tag == 'strong':
            self.md_file += '**'
        elif tag == 'ul':
            self.temp_tag = 'ul'
            self.md_file += '  \n'
        elif tag == 'ol':
            self.ol_count = 0
            self.temp_tag = 'ol'
            self.md_file += '  \n'
        elif tag == 'li':
            if self.temp_tag == 'ul':
                self.md_file += '* '
            elif self.temp_tag == 'ol':
                self.ol_count += 1
                self.md_file += f'{self.ol_count}. '
        elif tag == 'div':
            self.div_count += 1
            attrs_dict = dict(attrs)
            if 'style' in attrs_dict and 'codeblock' in attrs_dict['style']:
                self.code_box_div_num = self.div_count
                self.code_box = True
                self.md_file += '```\n'
            elif 'class' in attrs_dict:
                self.class_div_count = self.div_count
                self.ignore_div = True
        elif tag == 'en-codeblock':
            self.code_box = True
            self.md_file += '\n```\n'
        elif tag == 'a':
            self.is_link = True
            attrs_dict = dict(attrs)
            self.link_ref = attrs_dict.get('href', '#')
            if not self.link_ref.startswith('http') and not self.link_ref.endswith('html') and not '@' in self.link_ref:
                self.related_data.append(self.link_ref)
        elif tag == 'style':
            self.ignore_data = True
        elif tag == 'symbol':
            self.ignore_data = True
        elif tag == 'svg':
            self.ignore_data = True
        elif tag == 'path':
            self.ignore_data = True
        elif tag == 'img':
            attrs_dict = dict(attrs)
            img_ref = attrs_dict['src']
            alt_name = attrs_dict['alt'] if 'alt' in attrs_dict else 'Placeholder'
            if self.is_link:
                self.related_data.append(img_ref)
                self.md_file += f'[![{alt_name}]({img_ref})]({self.link_ref})'
            else:
                self.related_data.append(img_ref)
                self.md_file += f'![{alt_name}]({img_ref})'
        elif tag == 'table':
            self.ignore_data = True
            self.table_start = self.getpos()

    def get_rawdata(self, start, stop, offset):
        temp_rawdata = self.rawdata
        for i in range(offset-1):
            next_section = temp_rawdata.find('\n')
            temp_rawdata = temp_rawdata[next_section+1:]
        return temp_rawdata[start:stop]

    def handle_endtag(self, tag):
        if tag == 'b' or tag == 'strong':
            self.md_file += '**  \n'
        elif tag == 'div':
            if self.code_box and self.code_box_div_num == self.div_count:
                self.code_box = False
                self.md_file += '```\n'
            elif self.ignore_div and self.class_div_count == self.div_count:
                self.ignore_div = False
            else:
                self.md_file += '  \n'
            self.div_count -= 1
        elif tag == 'en-codeblock':
            self.code_box = False
            self.md_file += '```\n'
        elif tag == 'a':
            self.is_link = False
        elif tag == 'style':
            self.ignore_data = False
        elif tag == 'symbol':
            self.ignore_data = False
        elif tag == 'svg':
            self.ignore_data = False
        elif tag == 'li':
            self.md_file += '  \n'
        elif tag == 'table':
            offset, lineno_stop = self.getpos()
            lineno_stop = lineno_stop + len(tag) + 3
            _, lineno_start = self.table_start
            raw_data = self.get_rawdata(lineno_start, lineno_stop, offset)
            self.md_file += '\n' + raw_data
            self.ignore_data = False

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.md_file += '  \n'
        elif tag == 'hr':
            self.md_file += '\n***  \n'
        elif tag == 'img':
            attr_dict = dict(attrs)
            name = attr_dict['data-filename']
            img_ref = attr_dict['src']
            self.related_data.append(img_ref)
            self.md_file += f'![{name}]({img_ref})'

    def handle_data(self, data):
        if self.is_link:
            self.md_file += f'[{data}]({self.link_ref})'
        elif self.ignore_data:
            pass
        else:
            self.md_file += data
