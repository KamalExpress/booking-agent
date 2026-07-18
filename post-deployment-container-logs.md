INFO:     172.28.0.4:45986 - "POST /api/v1/worker/stream-logs HTTP/1.1" 200 OK
INFO:     172.28.0.4:52072 - "POST /api/v1/worker/heartbeat HTTP/1.1" 200 OK
INFO:     172.28.0.4:59914 - "GET /api/v1/worker/assignments/next HTTP/1.1" 204 No Content
INFO:     172.28.0.4:59914 - "POST /api/v1/worker/stream-logs HTTP/1.1" 200 OK
INFO:     172.28.0.4:52996 - "POST /api/v1/worker/heartbeat HTTP/1.1" 200 OK
INFO:     172.28.0.4:50358 - "GET /api/v1/worker/assignments/next HTTP/1.1" 204 No Content
INFO:     172.28.0.4:50358 - "POST /api/v1/worker/stream-logs HTTP/1.1" 200 OK
INFO:     172.28.0.1:48124 - "GET /playbook HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/uvicorn/protocols/http/httptools_impl.py", line 422, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/uvicorn/middleware/proxy_headers.py", line 63, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/fastapi/applications.py", line 1163, in __call__
    await super().__call__(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 193, in __call__
    response = await self.dispatch_func(request, call_next)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 30, in add_no_cache_headers
    response = await call_next(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 168, in call_next
    raise app_exc from app_exc.__cause__ or app_exc.__context__
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 144, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py", line 88, in __call__
    await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 2685, in app
    await route.handle(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 1766, in handle
    await self.original_router.handle(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 2740, in handle
    await included_router._handle_selected(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 1786, in _handle_selected
    await original_route.handle(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 1265, in handle
    await app(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 151, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 137, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 691, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/fastapi/routing.py", line 345, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/routers/ui.py", line 64, in playbook_page
    return render_template("playbook.html", {"request": request, "user": user, "active_page": "playbook"}, db)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/routers/ui.py", line 53, in render_template
    return templates.TemplateResponse(request=context["request"], name=name, context=context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/starlette/templating.py", line 148, in TemplateResponse
    template = self.get_template(name)
               ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/starlette/templating.py", line 115, in get_template
    return self.env.get_template(name)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/jinja2/environment.py", line 1016, in get_template
    return self._load_template(name, globals)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/jinja2/environment.py", line 975, in _load_template
    template = self.loader.load(self, name, self.make_globals(globals))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/jinja2/loaders.py", line 138, in load
    code = environment.compile(source, name, filename)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/jinja2/environment.py", line 771, in compile
    self.handle_exception(source=source_hint)
  File "/usr/local/lib/python3.11/site-packages/jinja2/environment.py", line 942, in handle_exception
    raise rewrite_traceback_stack(source=source)
  File "/app/app/templates/playbook.html", line 3, in template
    {% block title %}Playbook - {{ branding.brand_name }}{% end %}
    ^^^^^^^^^^^^^^^^^^^^^^^^^
jinja2.exceptions.TemplateSyntaxError: Encountered unknown tag 'end'. Jinja was looking for the following tags: 'endblock'. The innermost block that needs to be closed is 'block'.