from mitama.http import Response, get_session
from mitama.app import Template, PackageLoader, Environment
from mitama.auth import password_auth, AuthorizationError

env = Environment(loader = PackageLoader(__package__, './templates'))

async def home(request):
    template = env.get_template('home.html')
    return Response.render(template)

async def login(request):
    data = {}
    if request.method == 'POST':
        post = request.post()
        screen_name = post['screen_name'] or ''
        password = post['password'] or ''
        data['screen_name'] = screen_name
        data['password'] = password
        try:
            result = password_auth(screen_name, password)
            sess = get_session(request)
            sess['jwt_token'] = result.getJWT()
            redirect_to = request.query['redirect_to'] or ''
            return Response(
                headers=[
                    'Location: '+redirect_to
                ]
            )
        except AuthorizationError as err:
            data['error'] = 'パスワード、またはログイン名が間違っています'
    template = env.get_template('login.html')
    return Response.render(template, data)

