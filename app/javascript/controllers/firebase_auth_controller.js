import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { sessionUrl: String }
  static targets = [ "error", "button" ]

  connect() {
    if (typeof firebase === "undefined") {
      this.showError("Firebase SDK failed to load.")
    }
  }

  signIn() {
    this.clearError()
    this.setStatus("Opening Google sign-in…")

    const provider = new firebase.auth.GoogleAuthProvider()
    firebase.auth().signInWithPopup(provider)
      .then(result => {
        this.setStatus("Signing in…")
        return result.user.getIdToken()
      })
      .then(token => this.postToken(token))
      .catch(error => {
        if (error.code === "auth/popup-closed-by-user") {
          this.setStatus("")
        } else {
          this.showError(`${error.code}: ${error.message}`)
        }
      })
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
