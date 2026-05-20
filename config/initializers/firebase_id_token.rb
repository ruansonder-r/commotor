FirebaseIdToken.configure do |config|
  config.project_ids = [ "commoter" ]
  config.redis = Redis.new(url: ENV["REDIS_URL"]) if ENV["REDIS_URL"]
end
