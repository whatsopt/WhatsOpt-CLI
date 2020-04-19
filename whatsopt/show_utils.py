from xdsmjs import bundlejs, css

HTML_TEMPLATE = """
<!doctype html>

<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<style type="text/css">
{}
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
        noDefaultDriver: true,
        noTitleTooltip: false,
      }};
      xdsmjs.XDSMjs(config).createXdsm(mdo);
    }});
</script>
</head>

<body>
    <div class="xdsm-toolbar"></div>
    <div class="xdsm2"></div>
</body>

</html>
"""


def show(xdsm):
    html = generate_html(xdsm)

    with open("xdsm.html", "w") as f:
        f.write(html)


def generate_html(xdsm):
    html = HTML_TEMPLATE.format(css(), bundlejs(), xdsm)
    return html
