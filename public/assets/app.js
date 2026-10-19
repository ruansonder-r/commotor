// Commoter front-end. Two behaviours and a service-worker registration — the
// Stimulus controllers from the Rails app, rewritten as delegated listeners so
// they survive Turbo's body swaps without needing a framework.
(function () {
  "use strict";

  // --- Theme toggle ---------------------------------------------------------

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (e) {}
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.textContent = theme === "dark" ? "☀" : "☾";
    });
  }

  function syncThemeButtons() {
    applyTheme(currentTheme());
  }

  // --- Firebase Google sign-in ---------------------------------------------

  function container() {
    return document.querySelector("[data-firebase-auth]");
  }

  function setStatus(message) {
    var button = document.querySelector("[data-firebase-auth-button]");
    if (!button) return;
    button.disabled = Boolean(message);
    button.textContent = message || "Sign in with Google";
  }

  function showError(message) {
    setStatus("");
    var target = document.querySelector("[data-firebase-auth-error]");
    if (!target) return;
    target.style.color = "var(--color-danger)";
    target.textContent = message;
    target.hidden = false;
  }

  function clearError() {
    var target = document.querySelector("[data-firebase-auth-error]");
    if (!target) return;
    target.hidden = true;
    target.textContent = "";
  }

  function postToken(token) {
    var node = container();
    var url = (node && node.dataset.sessionUrl) || "/session";
    var csrf = document.querySelector('meta[name="csrf-token"]');

    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf ? csrf.content : ""
      },
      body: JSON.stringify({ firebase_token: token })
    })
      .then(function (response) {
        if (response.ok) {
          window.location.replace("/dashboard");
          return;
        }
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (body) {
            showError(body.error || "Server error " + response.status);
          });
      })
      .catch(function (error) {
        showError("Network error: " + error.message);
      });
  }

  function signIn() {
    if (typeof firebase === "undefined" || !firebase.apps.length) {
      showError("Firebase SDK failed to load.");
      return;
    }
    clearError();
    setStatus("Opening Google sign-in…");

    var provider = new firebase.auth.GoogleAuthProvider();
    firebase
      .auth()
      .signInWithPopup(provider)
      .then(function (result) {
        setStatus("Signing in…");
        return result.user.getIdToken();
      })
      .then(postToken)
      .catch(function (error) {
        if (error.code === "auth/popup-closed-by-user") {
          setStatus("");
        } else {
          showError(error.code + ": " + error.message);
        }
      });
  }

  // --- Wiring ---------------------------------------------------------------

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-theme-toggle]")) {
      event.preventDefault();
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
      return;
    }
    if (event.target.closest("[data-firebase-auth-button]")) {
      event.preventDefault();
      signIn();
    }
  });

  document.addEventListener("DOMContentLoaded", syncThemeButtons);
  document.addEventListener("turbo:load", syncThemeButtons);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {
        // A failed registration costs nothing — the app still works online.
      });
    });
  }
})();
