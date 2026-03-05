
import sys
sys.path.insert(0, r'd:\Automotive-Mobile-Device-Management-Platform')
from admin_service.app import app
app.run(host='0.0.0.0', port=5001, threaded=True, debug=False)
