from kaolalabot.server import create_app
app = create_app()
paths = sorted({r.path for r in app.routes if r.path.startswith('/api/system')})
for p in paths:
    print(p)
print('count=', len(paths))
