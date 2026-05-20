class TripLogsController < ApplicationController
  before_action :set_group

  def create
    @trip_log = @group.trip_logs.build(recorded_by: current_user)

    if @trip_log.save
      @memberships = @group.memberships.includes(:user)
      respond_to do |format|
        format.turbo_stream
        format.html { redirect_back fallback_location: dashboard_path }
      end
    else
      redirect_back fallback_location: dashboard_path,
                    alert: @trip_log.errors.full_messages.to_sentence
    end
  end

  def decrement
    if @group.trip_logs.sum(:trip_count).to_i <= 0
      redirect_to carpool_group_path(@group), alert: "Already at zero trips."
      return
    end

    @trip_log = @group.trip_logs.build(recorded_by: current_user, trip_count: -1)

    if @trip_log.save
      @memberships = @group.memberships.includes(:user)
      respond_to do |format|
        format.turbo_stream { render :create }
        format.html { redirect_to carpool_group_path(@group) }
      end
    else
      redirect_to carpool_group_path(@group),
                  alert: @trip_log.errors.full_messages.to_sentence
    end
  end

  private

  def set_group
    @group = current_user.carpool_groups.find(params[:carpool_group_id])
  end
end
