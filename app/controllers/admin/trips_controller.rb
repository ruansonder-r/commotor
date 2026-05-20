class Admin::TripsController < Admin::BaseController
  before_action :set_trip, only: [ :edit, :update, :destroy ]

  def index
    @trips = Trip.all.order(:name)
  end

  def new
    @trip = Trip.new
  end

  def create
    @trip = Trip.new(trip_params)
    if @trip.save
      redirect_to admin_trips_path, notice: "Trip added."
    else
      render :new, status: :unprocessable_entity
    end
  end

  def edit
  end

  def update
    if @trip.update(trip_params)
      redirect_to admin_trips_path, notice: "Trip updated."
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    if @trip.destroy
      redirect_to admin_trips_path, notice: "Trip removed."
    else
      redirect_to admin_trips_path, alert: @trip.errors.full_messages.to_sentence
    end
  end

  private

  def set_trip
    @trip = Trip.find(params[:id])
  end

  def trip_params
    params.require(:trip).permit(:name, :distance_km)
  end
end
