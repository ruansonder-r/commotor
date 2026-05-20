class SessionsController < ApplicationController
  skip_before_action :authenticate_user!, only: [ :new, :create ]

  # Skip CSRF for the token POST — the request comes from the native Android layer,
  # not from a form in a browser session.
  protect_from_forgery with: :null_session, only: [ :create ]

  def new
  end

  def create
    payload = FirebaseIdToken::Signature.verify(params[:token])

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
    redirect_to new_session_path
  end
end
