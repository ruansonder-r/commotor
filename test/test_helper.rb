ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
require "rails/test_help"
module ActiveSupport
  class TestCase
    parallelize(workers: :number_of_processors)
    fixtures :all
  end
end

# Minitest 6 removed minitest/mock. Provide a minimal class-method stub using
# Ruby's define_singleton_method so tests don't need an extra mock gem.
module ClassMethodStub
  def stub_class_method(klass, method_name, return_value)
    original = klass.method(method_name)
    klass.define_singleton_method(method_name) { |*| return_value }
    yield
  ensure
    klass.define_singleton_method(method_name, original)
  end
end

module AuthTestHelper
  include ClassMethodStub

  # Stubs Firebase verification and POSTs to /session so controller tests
  # get a real cookie-backed session identical to what the app uses.
  def sign_in_as(user)
    payload = { "user_id" => user.uid, "name" => user.display_name, "email" => user.email }
    stub_class_method(FirebaseIdToken::Signature, :verify, payload) do
      post session_path, params: { token: "stub" }
    end
  end
end

class ActionDispatch::IntegrationTest
  include AuthTestHelper
end
