import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { sessionUrl: String }
  static targets = [ "error" ]

  async signIn() {
    this.clearError()
    const provider = new firebase.auth.GoogleAuthProvider()

    try {
      const result = await firebase.auth().signInWithPopup(provider)
      const token = await result.user.getIdToken()

      const csrf = document.querySelector('meta[name="csrf-token"]')?.content
      const response = await fetch(this.sessionUrlValue, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ firebase_token: token })
      })

      if (response.ok) {
        window.location.href = "/dashboard"
      } else {
        const body = await response.json().catch(() => ({}))
        this.showError(body.error || `Sign-in failed (${response.status})`)
      }
    } catch (error) {
      if (error.code !== "auth/popup-closed-by-user") {
        this.showError(error.message)
      }
    }
  }

  showError(message) {
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
}
