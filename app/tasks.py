import json
import sys
import time
from flask import render_template
#from rq import get_current_job
from app import create_app, db,make_celery
from app.models import User, Post, Task
from app.email import send_email
from celery.result import AsyncResult

app = create_app()
app.app_context().push()

celery = make_celery(app)

@celery.task
def _set_task_progress(progress,task_id):
    task_temp = Task.query.get(task_id)
    task_temp.user.add_notification('task_progress', {'task_id': task_id,
                                                    'progress': progress})
    if progress >= 100:
        task_temp.complete = True
    db.session.commit()

@celery.task(bind=True)
def export_posts_c(self,user_id,task_id):
    try:
        
        _set_task_progress(0,task_id)
        self.update_state(state=0)
        data = []
        i = 0
        user = User.query.get(user_id)
        total_posts = user.posts.count()
        # for j in range(1,total_posts):
        #     _set_task_progress(j,task_id)
        #     self.update_state(state=j)
        #     time.sleep(1)
        for post in user.posts.order_by(Post.timestamp.asc()):
            data.append({'body': post.body,
                         'timestamp': post.timestamp.isoformat() + 'Z'})
            time.sleep(1)
            i += 1
            _set_task_progress(100 * i // total_posts,task_id)
            self.update_state(state=100 * i // total_posts)
        send_email('[Microblog] Your blog posts',
                sender=app.config['ADMINS'][0], recipients=[user.email],
                text_body=render_template('email/export_posts.txt', user=user),
                html_body=render_template('email/export_posts.html',
                                          user=user),
                attachments=[('posts.json', 'application/json',
                              json.dumps({'posts': data}, indent=4))],
                sync=True)
    except:
        _set_task_progress(100,task_id)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
