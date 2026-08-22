import os
import click
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash
from werkzeug.utils import safe_join
from flask_login import LoginManager, current_user

from extensions import db, csrf
from models import User, UserSettings, Folder, ResourceShare, ShareRole
from api import api_bp

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
csrf.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db.init_app(app)

login_manager = LoginManager(app)
# No login_view: nothing here uses Flask-Login's @login_required / automatic
# redirect flow -- require_login() below handles auth-gating manually, and
# the React app's own RequireAuth handles client-side redirect to /login.


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.cli.command('create-user')
@click.argument('username')
@click.option('--admin', is_flag=True, help='Grant this user admin rights.')
def create_user(username, admin):
    """Create a new user account."""
    if User.query.filter_by(username=username).first():
        click.echo(f'User "{username}" already exists.')
        return
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    user = User(username=username, password_hash=generate_password_hash(password), is_admin=admin)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserSettings(user_id=user.id))
    db.session.commit()
    click.echo(f'Created user "{username}"{" (admin)" if admin else ""}.')


@app.cli.command('list-users')
def list_users_cli():
    """List all user accounts."""
    users = User.query.order_by(User.username).all()
    if not users:
        click.echo('No users yet. Create one with: flask create-user <username>')
        return
    for user in users:
        click.echo(f'{user.username}{" (admin)" if user.is_admin else ""} - created {user.created_at}')


@app.cli.command('reset-password')
@click.argument('username')
def reset_password(username):
    """Reset a user's password."""
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f'No user "{username}".')
        return
    password = click.prompt('New password', hide_input=True, confirmation_prompt=True)
    user.password_hash = generate_password_hash(password)
    db.session.commit()
    click.echo(f'Password updated for "{username}".')


@app.cli.command('list-books')
def list_books_cli():
    """List all books with their id and owner, for use with share-book."""
    books = Folder.query.filter_by(parent_id=None).order_by(Folder.id).all()
    if not books:
        click.echo('No books yet.')
        return
    for book in books:
        owner = db.session.get(User, book.owner_id)
        owner_name = owner.username if owner else '(no owner)'
        click.echo(f'{book.id}: "{book.name}" - owned by {owner_name}')


@app.cli.command('share-book')
@click.argument('book_id', type=int)
@click.argument('username')
@click.argument('role', type=click.Choice(['editor', 'viewer']))
def share_book_cli(book_id, username, role):
    """Grant a user access to a book. See: flask list-books"""
    book = Folder.query.filter_by(id=book_id, parent_id=None).first()
    if not book:
        click.echo(f'No book with id {book_id}. See: flask list-books')
        return
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f'No user "{username}".')
        return
    if book.owner_id == user.id:
        click.echo(f'{username} already owns this book.')
        return
    share = ResourceShare.query.filter_by(folder_id=book_id, user_id=user.id).first()
    if share:
        share.role = ShareRole(role)
    else:
        db.session.add(ResourceShare(folder_id=book_id, user_id=user.id, role=ShareRole(role)))
    db.session.commit()
    click.echo(f'Shared "{book.name}" with {username} as {role}.')


@app.cli.command('unshare-book')
@click.argument('book_id', type=int)
@click.argument('username')
def unshare_book_cli(book_id, username):
    """Revoke a user's access to a book."""
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f'No user "{username}".')
        return
    share = ResourceShare.query.filter_by(folder_id=book_id, user_id=user.id).first()
    if not share:
        click.echo(f'{username} does not have direct access to book {book_id}.')
        return
    db.session.delete(share)
    db.session.commit()
    click.echo(f'Revoked {username}\'s access to book {book_id}.')


app.register_blueprint(api_bp)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')


@app.route('/healthz')
def healthz():
    return ('', 204)


PUBLIC_API_ENDPOINTS = {'api.api_login', 'api.api_get_invite', 'api.api_accept_invite'}


@app.before_request
def require_login():
    # Only /api/* needs a server-side auth gate. The SPA shell itself (static
    # files, index.html) is always servable -- the React app gates its own
    # UI client-side and simply gets 401s from the API if not logged in.
    if not request.path.startswith('/api/'):
        return
    if request.endpoint in PUBLIC_API_ENDPOINTS:
        return
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    full_path = safe_join(FRONTEND_DIST, path) if path else None
    if full_path and os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
