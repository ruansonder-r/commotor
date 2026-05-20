class CarpoolGroupsController < ApplicationController
  before_action :set_group

  def show
    @memberships = @group.memberships.includes(:user)
    @trip_log = @group.trip_logs.build
  end

  private

  def set_group
    @group = current_user.carpool_groups.find(params[:id])
  end
end
