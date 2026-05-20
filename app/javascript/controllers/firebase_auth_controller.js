import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { sessionUrl: String }
  static targets = [ "error", "button" ]

  connect() {
    if (typeof firebase === "undefined") {
      this.showError("Firebase SDK failed to load.")
      return
    }

    // If this is an explicit sign-out visit, sign out of Firebase too
    // so onAuthStateChanged doesn't immediately re-sign the user in.
    const params = new URLSearchParams(window.location.search)
    if (params.get("signout")) {
      firebase.auth().signOut().then(() => {
        window.history.replaceState({}, "", "/session/new")
      })
      return
    }

    // After signInWithRedirect completes, Firebase updates auth state.
    // onAuthStateChanged is more reliable than getRedirectResult for picking this up.
    this.showInfo("Checking auth state…")
    firebase.auth().onAuthStateChanged(user => {
      if (user && !this.tokenPosted) {
        this.tokenPosted = true
        this.showInfo(`Auth OK (${user.email}) — creating session…`)
        user.getIdToken(true).then(token => this.postToken(token))
          .catch(error => this.showError(error.message))
      } else if (!user) {
        this.showInfo("")
      }
    })
  }

  signIn() {
    this.clearError()
    const provider = new firebase.auth.GoogleAuthProvider()
    firebase.auth().signInWithRedirect(provider)
      .catch(error => this.showError(error.message))
  }

  postToken(token) {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content
    return fetch(this.sessionUrlValue, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ firebase_token: token })
    })
    .then(response => {
      if (response.ok) {
        window.location.replace("/dashboard")
      } else {
        return response.json()
          .catch(() => ({}))
          .then(body => this.showError(body.error || `Server error ${response.status}`))
      }
    })
    .catch(error => this.showError(`Network error: ${error.message}`))
  }

  showInfo(message) {
    if (this.hasErrorTarget) {
      this.errorTarget.style.color = "var(--color-muted)"
      this.errorTarget.textContent = message
      this.errorTarget.hidden = !message
    }
  }

  showError(message) {
    this.setStatus("")
    if (this.hasErrorTarget) {
      this.errorTarget.style.color = "var(--color-danger)"
      this.errorTarget.textContent = message
      this.errorTarget.hidden = false
    }
  }

  clearError() {
    if (this.hasErrorTarget) {
      this.errorTarget.hidden = true
      this.errorTarget.textContent = ""
    }
  }

  setStatus(message) {
    if (this.hasButtonTarget) {
      this.buttonTarget.disabled = !!message
      this.buttonTarget.textContent = message || "Sign in with Google"
    }
  }
}
