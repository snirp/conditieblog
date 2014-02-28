import io
import yaml
import markdown as markdown_module
import pygments.formatters
import os
import werkzeug
import re
import itertools
from flask import Flask, Markup, render_template, abort, render_template_string, url_for
from flask_weasyprint import HTML

app = Flask(__name__)

PYGMENTS_CSS = (pygments.formatters.HtmlFormatter(style='tango').get_style_defs('.codehilite'))

#configuration
app.config['FREEZER_DESTINATION'] = 'gh-pages'
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*', 'CNAME', '.gitignore', 'readme.md']
app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_BASE_URL'] = 'http://flatfreeze.com'  # freezer uses this for _external=True URLs

@app.template_filter()
def jinjatag(text):
    """allow jinja tags to be rendered in flat content"""
    return render_template_string(Markup(text))

@app.template_filter()
def markdown(text, extensions=['codehilite', 'fenced_code']):
    """render markdown to HTML, possibly using custom extensions"""
    return markdown_module.markdown(text, extensions)


#flatpage classes
class Pages(object):
    """
    Render flatpages with Flask: static site generator together with Frozen-Flask.
    An application can have multiple instances of Pages for different types
    of flatpages. Organize markup files in separate directories like 'blog' and
    'whitepages'. The filenames (minus suffix) should be valid url's.

    Add a YAML header to your Markdown files to set page-specific properties,
    such as: 'published', 'summary' or 'tags'.

    Caching is implemented for the properties and HTML content of the pages and
    for the automatically generated PDF files.

    Attributes:
        _cache          Stores Page-instance and last-modified per flatpage filepath.
        _pdfcache       Stores last-modified per PDF filepath.
        pdfdir          Directory that holds PDFs (in a subdir for each Pages instance).

    Arguments (instance specific):
        flatdir         Directory that holds the flat markup files.
        suffix          Only files with matching suffix are rendered.
    """
    _cache = {}
    _pdfcache = {}
    pdfdir = 'pdfcache'

    def __init__(self, flatdir='pages', suffix='.md'):
        self.flatdir = flatdir
        self.suffix = suffix

    def flatroot(self):
        return os.path.join(app.root_path, self.flatdir)

    def all_pages(self):
        """Generator that yiels a Page instance for every flatfile"""
        if not os.path.isdir(self.flatroot()):
            abort(404)
        for filename in os.listdir(self.flatroot()):
            if filename.endswith(self.suffix):
                yield self.get_page(filename[:-len(self.suffix)])

    def get_pdf(self, name):
        """
        Return a pdf file object for a Page instance.
        Create a pdf if no pdf exists or the underlying flatfile is more recent.
        Update the pdfcache after creating or updating a pdf.
        """
        flatpath = os.path.join(self.flatroot(), name+self.suffix)
        pdfpath = os.path.join(app.root_path, self.pdfdir, self.flatdir, name+'.pdf')
        if not os.path.isfile(pdfpath):
            try:
                HTML(self.get_page(name).url()).write_pdf(pdfpath)
            except IOError:
                abort(500)  # check if folder exists and you have write permission
            self._pdfcache[pdfpath] = os.path.getmtime(pdfpath)
        else:
            flat_mtime = os.path.getmtime(flatpath)
            if flat_mtime > os.path.getmtime(pdfpath):  # flatfile is more recent > new pdf
                try:
                    HTML(self.get_page(name).url()).write_pdf(pdfpath)
                except IOError:
                    abort(500)  # check if folder exists and you have write permission
                self._pdfcache[pdfpath] = os.path.getmtime(pdfpath)
        return open(pdfpath).read()

    def get_page(self, name):
        """
        Return a Page instance from cache or instantiate a new one if outdated or absent.
        The file content is split in a (Markdown) body and (YAML) head section.
        Update the cache with the new or updated Page instance.
        """
        filepath = os.path.join(self.flatroot(), name+self.suffix)
        if not os.path.isfile(filepath):
            abort(404)
        mtime = os.path.getmtime(filepath)
        page, old_mtime = self._cache.get(filepath, (None, None))
        if not page or mtime != old_mtime:
            with io.open(filepath, encoding='utf8') as fd:
                head = ''.join(itertools.takewhile(lambda x: x.strip(), fd))
                body = fd.read()
            page = Page(name, head, body, self.flatdir)
            self._cache[filepath] = (page, mtime)
        return page


class Page(object):
    """


    Arguments (instance specific):
        name            Derived from filename of the flatfile.
        head            String to be rendered as YAML to properties
        body            String to be rendered as Markdown to HTML
        flatdir         Used to match Page object to its url's
    """

    def __init__(self, name, head, body, flatdir):
        self.name = name
        self.head = head
        self.body = body
        self.flatdir = flatdir

    def __getitem__(self, name):
        """getter to access the meta properties directly"""
        return self.meta.get(name)

    @werkzeug.cached_property
    def meta(self):
        """Render head section of file to meta properties."""
        return yaml.safe_load(self.head) or {}

    @werkzeug.cached_property
    def html(self):
        """Render Markdown and Jinja tags to HTML."""
        return markdown_module.markdown(render_template_string(Markup(self.body)),
                                        ['codehilite', 'fenced_code'])

    def lastmod(self):
        return self.meta.get('updated', self['published'])

    def url(self, **kwargs):
        return url_for(self.flatdir+'_detail', name=self.name, **kwargs)

    def pdf(self, **kwargs):
        return url_for(self.flatdir+'_pdf', name=self.name, **kwargs)

#instantiate flatpage class
blog = Pages('blog')
tip = Pages('tip')


#helper functions: ordering and filtering
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

@app.route('/contact.html')
def contact():
    pageid = 'contact'
    return render_template('contact.html', **locals())

@app.route('/blog/index.html')
def blog_index():
    blogs = [b for b in published(blog.all_pages())]
    pageid = 'blog'
    return render_template('blog-list.html', **locals())

@app.route('/blog/atom.xml')
def blog_feed():
    articles = sorted(published(blog.all_pages()), key=lambda a: a.lastmod())[:10]
    feed_updated = articles[0].lastmod()
    xml = render_template('atom.xml', **locals())
    return app.response_class(xml, mimetype='application/atom+xml')

@app.route('/blog/<name>.html')
def blog_detail(name):
    b = blog.get_page(name)
    pageid = 'blog'
    return render_template('blog-detail.html', **locals())

@app.route('/blog/<name>.pdf')
def blog_pdf(name):
    pdf = blog.get_pdf(name)
    return app.response_class(pdf, mimetype="application/pdf")

@app.route('/tip/index.html')
def tip_index():
    tips = [t for t in published(tip.all_pages())]
    pageid = 'tip'
    return render_template('tip-list.html', **locals())

@app.route('/tip/atom.xml')
def tip_feed():
    articles = sorted(published(tip.all_pages()), key=lambda a: a.lastmod())[:10]
    feed_updated = articles[0].lastmod()
    xml = render_template('atom.xml', **locals())
    return app.response_class(xml, mimetype='application/atom+xml')

@app.route('/tip/<name>.html')
def tip_detail(name):
    t = tip.get_page(name)
    pageid = 'tip'
    return render_template('tip-detail.html', **locals())

@app.route('/tip/<name>.pdf')
def tip_pdf(name):
    pdf = tip.get_pdf(name)
    return app.response_class(pdf, mimetype="application/pdf")

@app.route('/draft/')
def draft_index():
    drafts = [t for t in draft(tip.all_pages())] + [b for b in draft(blog.all_pages())]
    return render_template('draft-list.html', **locals())


@app.route('/sitemap.xml')
def generate_sitemap():
    sites = [
        (url_for('home', _external=True),       '2014-02-13'),
        (url_for('contact', _external=True),    '2014-02-13'),
        (url_for('blog_index', _external=True), '2014-02-13'),
        (url_for('blog_feed', _external=True),  '2014-02-15'),
        (url_for('tip_index', _external=True),  '2014-02-13'),
        (url_for('tip_feed', _external=True),   '2014-02-15')
    ]
    sites = [(s[0], s[1]) for s in sites] + \
            [(b.url(_external=True), b.lastmod()) for b in published(blog.all_pages())] + \
            [(t.url(_external=True), t.lastmod()) for t in published(tip.all_pages())]
    xml = render_template('sitemap.xml', **locals())
    return app.response_class(xml, mimetype='application/atom+xml')


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

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html')


@app.route('/404.html')
def error_freeze():
    """explicitly set a route so that 404.html exists in gh-pages"""
    return render_template('404.html')


#launch
if __name__ == "__main__":
    app.run(debug=True)