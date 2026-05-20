import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["toggle"]

  connect() {
    this.applyTheme(localStorage.getItem("theme") || "light")
  }

  toggle() {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"
    this.applyTheme(next)
    localStorage.setItem("theme", next)
  }

  applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme)
    if (this.hasToggleTarget) {
      this.toggleTarget.textContent = theme === "dark" ? "☀" : "☾"
    }
  }
}
