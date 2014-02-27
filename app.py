<<<<<<< HEAD
import io
import yaml
import markdown as markdown_module
import pygments.formatters
import os
import werkzeug

import re
import itertools
from flask import Flask, Markup, render_template, abort, render_template_string, url_for
from flask_weasyprint import render_pdf

app = Flask(__name__)

HOSTING_DOMAIN = 'http://snirp.nl'
PYGMENTS_CSS = (pygments.formatters.HtmlFormatter(style='tango')
                .get_style_defs('.codehilite'))
=======
from flask import Flask, render_template, Markup, render_template_string, url_for
from flask_flatpages import FlatPages, pygmented_markdown
from werkzeug.contrib.atom import AtomFeed

#initialization
app = Flask(__name__)
blogs = FlatPages(app)


#configuration
def prerender_jinja(text):
    return pygmented_markdown(render_template_string(Markup(text)))

app.config['FLATPAGES_ROOT'] = 'blog'
app.config['FLATPAGES_EXTENSION'] = '.md'
app.config['FLATPAGES_HTML_RENDERER'] = prerender_jinja
>>>>>>> d15a49f4c572324fa712ff29f0f3f732e1b11b14

app.config['FREEZER_DESTINATION'] = 'gh-pages'
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*', 'CNAME', '.gitignore', 'readme.md']
app.config['FREEZER_RELATIVE_URLS'] = True
<<<<<<< HEAD
app.config['FREEZER_BASE_URL'] = 'http://snirp.nl'

@app.template_filter()
def markdown(text):
    return markdown_module.markdown(text, ['codehilite', 'fenced_code'])

@app.template_filter()
def jinjatag(text):
    return render_template_string(Markup(text))


#platblad
class Pages(object):
    _cache = {}  # shared cache

    def __init__(self, folder='pages', suffix='.md'):
        self.folder = folder
        self.suffix = suffix

    def root(self):
        return os.path.join(app.root_path, self.folder)

    def all(self):
        pagedir = os.path.join(self.root())
        if not os.path.isdir(pagedir):
            abort(404)
        for filename in os.listdir(pagedir):
            if filename.endswith(self.suffix):
                yield self.get(filename[:-len(self.suffix)])

    def get(self, name):
        filepath = os.path.join(self.root(), name+self.suffix)
        if not os.path.isfile(filepath):
            abort(404)
        mtime = os.path.getmtime(filepath)
        page, old_mtime = self._cache.get(filepath, (None, None))
        if not page or mtime != old_mtime:
            with io.open(filepath, encoding='utf8') as fd:
                head = ''.join(itertools.takewhile(lambda x: x.strip(), fd))
                body = fd.read()
            page = Page(name, head, body, self.folder)
            self._cache[filepath] = (page, mtime)
        return page


class Page(object):

    def __init__(self, name, head, body, folder):
        self.name = name
        self.head = head
        self.body = body
        self.folder = folder

    def __getitem__(self, name):
        return self.meta.get(name)

    @werkzeug.cached_property
    def meta(self):
        return yaml.safe_load(self.head) or {}

    @werkzeug.cached_property
    def html(self):
        return markdown_module.markdown(render_template_string(Markup(self.body)), ['codehilite', 'fenced_code'])

    def lastmod(self):
        return self.meta.get('updated', self['published'])

    def url(self, **kwargs):
        return url_for(self.folder+'_detail', name=self.name, **kwargs)

    def pdf(self, **kwargs):
        return url_for(self.folder+'_pdf', name=self.name, **kwargs)

blog = Pages('blog')
tip = Pages('tip')


def draft(pages):
    return [p for p in pages if not p['published']]


def published(pages):
    """filter published pages, sort by published and slice to limit"""
    return sorted([p for p in pages if p['published']], reverse=True, key=lambda p: p['published'])


#views
@app.route('/')
def home():
    pageid = 'home'
    return render_template('index.html', **locals())

@app.route('/contact')
def contact():
    pageid = 'contact'
    return render_template('contact.html', **locals())

@app.route('/blog/')
def blog_index():
    blogs = [b for b in published(blog.all())]
    return render_template('blog-list.html', **locals())

@app.route('/blog/atom.xml')
def blog_feed():
    articles = sorted(published(blog.all()), key=lambda a: a.lastmod())[:10]
    feed_updated = articles[0].lastmod()
    xml = render_template('atom.xml', **locals())
    return app.response_class(xml, mimetype='application/atom+xml')

@app.route('/blog/<name>')
def blog_detail(name):
    b = blog.get(name)
    return render_template('blog-detail.html', **locals())

@app.route('/blog/<name>.pdf')
def blog_pdf(name):
    return render_pdf(url_for('blog_detail', name=name))

@app.route('/tips/')
def tip_index():
    tips = [t for t in published(tip.all())]
    pageid = 'tips'
    return render_template('tip-list.html', **locals())

@app.route('/tips/<name>')
def tip_detail(name):
    t = tip.get(name)
    pageid = 'tips'
    return render_template('tip-detail.html', **locals())

@app.route('/tip/<name>.pdf')
def tip_pdf(name):
    return render_pdf(url_for('tip_detail', name=name))

@app.route('/draft/')
def draft_index():
    drafts = [t for t in draft(tip.all())] + [b for b in draft(blog.all())]
    return render_template('draft-list.html', **locals())


@app.route('/sitemap.xml')
def generate_sitemap():
    sites = [
        (url_for('home'),      '2014-02-13'),
        (url_for('contact'),    '2014-02-13'),
        (url_for('blog_index'), '2014-02-13'),
        #(url_for('blog_feed'),  '2014-02-15'),
        (url_for('tip_index'),  '2014-02-13'),
        #(url_for('tip_feed'),   '2014-02-15')
    ]
    sites = [(HOSTING_DOMAIN + s[0], s[1]) for s in sites] + \
            [(HOSTING_DOMAIN + b.url(), b.lastmod()) for b in published(blog.all())] + \
            [(HOSTING_DOMAIN + t.url(), t.lastmod()) for t in published(tip.all())]
    return render_template('sitemap.xml', sites=sites)


def minify_css(css):
    # Remove comments. *? is the non-greedy version of *
    css = re.sub(r'/\*.*?\*/', '', css)
    # Remove redundant whitespace
    css = re.sub(r'\s+', ' ', css)
    # Put back line breaks after block so that it's not just one huge line
    css = re.sub(r'} ?', '}\n', css)
    return css

@app.route('/style.css')
def stylesheet():
    css = render_template('style.css', pygments_css=PYGMENTS_CSS)
    css = minify_css(css)
    return app.response_class(css, mimetype='text/css')

=======

HOSTING_DOMAIN = 'http://flatfreeze.com'

#controllers
@app.route("/")
def index():
    blog_list = page_list(blogs, 3)
    return render_template('index.html', blog_list=blog_list)

@app.route('/contact.html')
def contact():
    return render_template('contact.html')

def page_list(pages, limit=None):
    p_list = (p for p in pages if 'published' in p.meta)
    p_list = sorted(p_list, reverse=True, key=lambda p: p.meta['published'])
    return p_list[:limit]

@app.route('/blog.html')
def blog_index():
    blog_list = page_list(blogs)
    return render_template('blog-index.html', blog_list=blog_list)

@app.route('/blog/<path:path>.html')
def blog_detail(path):
    blog = blogs.get_or_404(path)
    return render_template('blog-detail.html', blog=blog)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/404.html')
def static_404():
    return render_template('404.html')

@app.route('/blog/atom.xml')
def blog_feed():
    feed = AtomFeed('Recent Blog Postings',
                    feed_url=HOSTING_DOMAIN+url_for('blog_feed'),
                    url=HOSTING_DOMAIN)
    blog_list = page_list(blogs, 10)
    for b in blog_list:
        feed.add(b.meta['title'],
                 content_type='html',
                 url=HOSTING_DOMAIN+'blog/'+b.path+'.html',
                 author=b.meta['author'],
                 updated=b.meta['lastmod'],
                 published=b.meta['published'],
                 summary=b.meta['description'])
    return feed.get_response()

@app.route('/sitemap.xml')
def generate_sitemap():
    locations = [
        (url_for('index'),      '2014-02-13'),
        (url_for('contact'),    '2014-02-13'),
        (url_for('blog_index'), '2014-02-13'),
        (url_for('blog_feed'),  '2014-02-15')
    ]
    sites = [(HOSTING_DOMAIN + l[0], l[1]) for l in locations] + \
            [(HOSTING_DOMAIN + '/blog/' + b.path + '.html', b.meta['lastmod']) for b in blogs]
    return render_template('sitemap.xml', sites=sites)

>>>>>>> d15a49f4c572324fa712ff29f0f3f732e1b11b14
#launch
if __name__ == "__main__":
    app.run(debug=True)