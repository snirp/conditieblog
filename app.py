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

app.config['FREEZER_DESTINATION'] = 'gh-pages'
app.config['FREEZER_DESTINATION_IGNORE'] = ['.git*', 'CNAME', '.gitignore', 'readme.md']
app.config['FREEZER_RELATIVE_URLS'] = True

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

#launch
if __name__ == "__main__":
    app.run(debug=True)