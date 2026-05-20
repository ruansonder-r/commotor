import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { sessionUrl: String }

  async signIn() {
    const provider = new firebase.auth.GoogleAuthProvider()

    try {
      const result = await firebase.auth().signInWithPopup(provider)
      const token = await result.user.getIdToken()
      await this.#postToken(token)
    } catch (error) {
      console.error("Google Sign-In error:", error.message)
    }
  }

  async #postToken(token) {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content
    const response = await fetch(this.sessionUrlValue, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ firebase_token: token })
    })

    if (response.ok) {
      window.location.href = "/dashboard"
    } else {
      console.error("Session creation failed", response.status)
    }
  }
}
