# WordPress Theme & Plugin

Scaffold correct, standards-compliant WordPress themes and plugins (PHP).

## Theme essentials
A minimal theme needs, in the theme folder:
- `style.css` with the theme header comment:
  ```
  /*
  Theme Name: My Theme
  Author: ...
  Version: 1.0.0
  */
  ```
- `index.php`, `header.php`, `footer.php`, `functions.php`.
- `functions.php`: enqueue styles/scripts via `wp_enqueue_style` / `wp_enqueue_script` on the `wp_enqueue_scripts` hook; register menus and `add_theme_support('title-tag','post-thumbnails')`.
- Use the Template Hierarchy (`single.php`, `page.php`, `archive.php`, `404.php`).
- Escape output (`esc_html`, `esc_url`, `esc_attr`) and use `wp_nonce` for forms.

## Plugin essentials
- A main PHP file with the plugin header comment (`Plugin Name:` ...).
- Hook with `add_action` / `add_filter`; prefix all functions to avoid collisions.
- Guard direct access: `if ( ! defined('ABSPATH') ) exit;`.
- Activation/deactivation hooks for setup/cleanup.

## Workflow
1. Create the folder structure with the files above.
2. Write clean, escaped PHP following WordPress coding standards.
3. Zip the theme/plugin folder for upload (`create_zip`) and confirm the path.
