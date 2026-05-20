module ApplicationHelper
  def firebase_web_config_json
    c = Rails.application.credentials.firebase[:web]
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
