<?php
// Dev-only Adminer entrypoint: replaces the image's own index.php (see
// docker-compose.override.yml) with one that connects and logs in
// automatically -- no server/username/password/db form, no click. This is
// only ever mounted for the local dev `adminer` service, never in
// production, so bypassing Adminer's own password check here is fine.
//
// A PHP file with a namespace block can't have code before it (other than
// declare()/comments), so everything -- including the pre-bootstrap $_GET
// tweak -- lives inside this single global-namespace block.
namespace {
	// Forces the Postgres driver regardless of how the URL is opened
	// (normally selected via a `?pgsql=` query param -- see
	// vendor/adminer/drivers/pgsql.inc.php).
	if (!isset($_GET['pgsql'])) {
		$_GET['pgsql'] = '';
	}

	function adminer_object() {
		// \Adminer\Adminer only exists once adminer.php's bootstrap has run,
		// which is what's calling this function -- so the class extending
		// it has to be declared in here (deferring the "extends" resolution
		// until call time), not at the top level of this file.
		// No type declarations on any of these -- the installed Adminer
		// version's own methods aren't typed either, and PHP requires an
		// override's parameter/return types to be compatible with the
		// parent's (mismatched typing here is a fatal "must be compatible
		// with" error, not just a lint complaint).
		final class DevAutoLoginAdminer extends \Adminer\Adminer {
			function credentials() {
				return array(
					getenv('ADMINER_AUTOLOGIN_SERVER') ?: 'db',
					getenv('ADMINER_AUTOLOGIN_USERNAME') ?: '',
					getenv('ADMINER_AUTOLOGIN_PASSWORD') ?: '',
				);
			}

			function database() {
				return getenv('ADMINER_AUTOLOGIN_DB') ?: null;
			}

			function login($login, $password) {
				return true;
			}

			// Print the normal <head> (styles, favicon, etc.) unchanged, then
			// auto-submit the login form the moment it appears -- the form's
			// fields are already prefilled by credentials() above, so this is
			// the only thing standing between loading the page and being in.
			// Adminer sends a strict per-request CSP (script-src 'nonce-...'
			// 'strict-dynamic'), so a plain <script> tag gets silently
			// blocked -- \Adminer\script() is the vendor's own helper for
			// emitting an inline script with that nonce attached.
			function head($dark = null) {
				$return = parent::head($dark);
				// This prints into <head>, before <body> (and the login
				// form in it) exists -- wait for DOMContentLoaded rather
				// than querying immediately, or the form is never found.
				echo \Adminer\script(
					'document.addEventListener("DOMContentLoaded", function () {'
					. 'var u = document.querySelector(\'input[name="auth[username]"]\');'
					. 'if (u && u.form) { u.form.submit(); }'
					. '});'
				);
				return $return;
			}
		}

		return new DevAutoLoginAdminer;
	}

	require('adminer.php');
}
