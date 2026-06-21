/* Shared nav login-state: turns "Sign in" into Account + credit balance (+ Admin). */
(function () {
  fetch('/api/site/config').then(function (r) { return r.json(); }).then(function (c) {
    document.querySelectorAll('.nav-right, .mobile-menu').forEach(function (box) {
      var signin = null;
      box.querySelectorAll('a').forEach(function (a) { if (a.textContent.trim() === 'Sign in') signin = a; });
      if (!signin) return;
      if (c.logged_in && c.user) {
        signin.textContent = 'Account';
        signin.href = '/account';
        var chip = document.createElement('a');
        chip.href = '/account';
        chip.className = signin.className;
        chip.style.cssText = 'display:inline-flex;gap:6px;align-items:center';
        chip.textContent = (c.user.credits).toLocaleString() + ' cr';
        signin.parentNode.insertBefore(chip, signin);
        if (c.user.is_admin) {
          var al = document.createElement('a');
          al.href = '/admin';
          al.className = signin.className;
          al.textContent = 'Admin';
          signin.parentNode.insertBefore(al, chip);
        }
      } else {
        signin.href = '/login';
      }
    });
  }).catch(function () {});
})();
