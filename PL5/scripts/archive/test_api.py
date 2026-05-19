import urllib.request
try:
    r = urllib.request.urlopen('http://localhost:8000/login')
    content = r.read().decode()
    print('Status Code:', r.status)
    print('Content Length:', len(content))
    if 'PL5' in content:
        print('Contains PL5 title: Yes')
    if 'login' in content.lower():
        print('Contains login form: Yes')
except Exception as e:
    print('Error:', e)
