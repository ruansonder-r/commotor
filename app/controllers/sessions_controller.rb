class SessionsController < ApplicationController
  skip_before_action :authenticate_user!, only: [ :new, :create ]

  # Skip CSRF for the token POST entirely — the Firebase ID token is already a
  # signed JWT that proves identity, so CSRF protection is redundant here.
  skip_before_action :verify_authenticity_token, only: [ :create ]

  def new
  end

  def create
    FirebaseIdToken::Certificates.request
    payload = FirebaseIdToken::Signature.verify(params[:firebase_token])

    if payload
      user = User.find_or_initialize_by(uid: payload["user_id"])
      user.assign_attributes(
        display_name: payload["name"].presence || "User",
        email: payload["email"]
      )
      user.save!

      session[:user_id] = user.id
      render json: { status: "ok" }, status: :created
    else
      render json: { error: "Invalid or expired token" }, status: :unauthorized
    end
  rescue StandardError => e
    render json: { error: e.message }, status: :unauthorized
  end

  def destroy
    session.delete(:user_id)
    redirect_to new_session_path(signout: 1)
  end
end
