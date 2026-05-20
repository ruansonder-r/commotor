class DashboardController < ApplicationController
  def index
    @carpool_groups = current_user.carpool_groups
                                  .includes(:car, :trip)
                                  .order(month: :desc)
  end
end
