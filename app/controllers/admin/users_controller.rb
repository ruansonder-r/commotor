class Admin::UsersController < Admin::BaseController
  def index
    @users = User.all.order(:display_name)
  end
end
