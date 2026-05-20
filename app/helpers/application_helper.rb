module ApplicationHelper
  def firebase_web_config_json
    firebase = Rails.application.credentials.firebase
    raise "Missing credentials: add a `firebase: web:` block via bin/rails credentials:edit" if firebase.nil?
    c = firebase[:web]
    raise "Missing credentials: firebase.web is not set — run bin/rails credentials:edit" if c.nil?
    {
      apiKey:            c[:api_key],
      authDomain:        c[:auth_domain],
      projectId:         c[:project_id],
      storageBucket:     c[:storage_bucket],
      messagingSenderId: c[:messaging_sender_id],
      appId:             c[:app_id]
    }.to_json
  end
end
