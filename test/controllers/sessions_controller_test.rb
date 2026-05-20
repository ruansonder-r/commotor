require "test_helper"

class SessionsControllerTest < ActionDispatch::IntegrationTest
  include ClassMethodStub

  test "GET new renders the login page without auth" do
    get new_session_path
    assert_response :success
  end

  test "POST create with a valid Firebase token creates session" do
    payload = { "user_id" => "uid_new", "name" => "New User", "email" => "new@example.com" }
    stub_class_method(FirebaseIdToken::Signature, :verify, payload) do
      post session_path, params: { firebase_token: "valid_token" }
    end
    assert_response :created
    assert_equal "ok", JSON.parse(response.body)["status"]
    assert User.exists?(uid: "uid_new")
  end

  test "POST create with a valid token for existing user does not duplicate the user" do
    alice = users(:alice)
    payload = { "user_id" => alice.uid, "name" => alice.display_name, "email" => alice.email }
    stub_class_method(FirebaseIdToken::Signature, :verify, payload) do
      assert_no_difference "User.count" do
        post session_path, params: { firebase_token: "valid_token" }
      end
    end
  end

  test "POST create with an invalid token returns 401" do
    stub_class_method(FirebaseIdToken::Signature, :verify, nil) do
      post session_path, params: { firebase_token: "bad_token" }
    end
    assert_response :unauthorized
    assert_includes JSON.parse(response.body)["error"], "Invalid"
  end

  test "DELETE destroy clears the session and redirects to login" do
    sign_in_as(users(:alice))
    delete session_path
    assert_redirected_to new_session_path
  end
end
