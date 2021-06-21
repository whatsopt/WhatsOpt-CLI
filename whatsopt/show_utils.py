from xdsmjs import bundlejs, css
from datetime import date

HTML_TEMPLATE = """
<!doctype html>

<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<style type="text/css">
{}

.footer {{
    font-style: italic;
    font-size: small;
    position: absolute;
    right: 20px;
}}
</style>
<script type="text/javascript">
{}
</script>
<script type="text/javascript">
    document.addEventListener('DOMContentLoaded', () => {{
      const mdo = {};
      const config = {{
        labelizer: {{
            ellipsis: 5,
            subSupScript: false,
            showLinkNbOnly: true,
        }},
        layout: {{
            origin: {{ x: 50, y: 20 }},
            cellsize: {{ w: 150, h: 50 }},
            padding: 10,
        }},
        withDefaultDriver: false,
      }};
      xdsmjs.XDSMjs(config).createXdsm(mdo);
    }});
</script>
</head>

<body>
    <div class="xdsm-toolbar"></div>
    <div class="xdsm2"></div>
    <hr>
    <div class="footer">{}</div>
</body>

</html>
"""


def generate_xdsm_html(source, xdsm, outfilename="xdsm.html"):
    html = _generate_html(source, xdsm)

    with open(outfilename, "w") as f:
        f.write(html)


def _generate_html(source, xdsm):
    footer = "XDSM generated from {}, {}, ONERA WhatsOpt".format(
        source, date.today().strftime("%b %d, %Y")
    )
    html = HTML_TEMPLATE.format(css(), bundlejs(), xdsm, footer)
    return html
