from kaolalabot.memory.manager import MemoryManager
from kaolalabot.server import create_app
print('MemoryManager import ok')
app = create_app()
print('server app import ok', len(app.routes))
