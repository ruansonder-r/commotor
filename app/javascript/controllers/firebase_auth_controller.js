import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { sessionUrl: String }
  static targets = [ "error", "button" ]

  connect() {
    // After Google redirects back to this page, pick up the result.
    if (typeof firebase === "undefined") {
      this.showError("Firebase SDK failed to load. Check your connection.")
      return
    }
    firebase.auth().getRedirectResult()
      .then(result => {
        if (result && result.user) {
          this.setLoading(true)
          return result.user.getIdToken().then(token => this.postToken(token))
        }
      })
      .catch(error => {
        if (error.code !== "auth/no-current-user") {
          this.showError(`${error.code}: ${error.message}`)
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
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ firebase_token: token })
    })
    .then(response => {
      if (response.ok) {
        window.location.href = "/dashboard"
      } else {
        return response.json()
          .catch(() => ({}))
          .then(body => {
            this.setLoading(false)
            this.showError(body.error || `Sign-in failed (${response.status})`)
          })
      }
    })
  }

  showError(message) {
    this.setLoading(false)
    if (this.hasErrorTarget) {
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

  setLoading(loading) {
    if (this.hasButtonTarget) {
      this.buttonTarget.disabled = loading
      this.buttonTarget.textContent = loading ? "Signing in…" : "Sign in with Google"
    }
  }
}
