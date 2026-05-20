class TripLogsController < ApplicationController
  before_action :set_group

  def create
    @trip_log = @group.trip_logs.build(recorded_by: current_user)

    if @trip_log.save
      redirect_back fallback_location: dashboard_path
    else
      redirect_back fallback_location: dashboard_path,
                    alert: @trip_log.errors.full_messages.to_sentence
    end
  end

  private

  def set_group
    @group = current_user.carpool_groups.find(params[:carpool_group_id])
  end
end
