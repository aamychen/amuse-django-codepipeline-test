from django.contrib.admin.widgets import AdminFileWidget


class AudioFileWidget(AdminFileWidget):
    def render(self, name, value, attrs=None, renderer=None):
        if value:
            return """<audio src="%s" controls>
                        <p>Your browser does not support the <code>audio</code> element.</p>
                    </audio>
                    <a href="%s">Download</a>""" % (
                value.url,
                value.url,
            )
