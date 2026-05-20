class Admin::CarpoolGroupsController < Admin::BaseController
  before_action :set_group, only: [ :edit, :update, :destroy ]

  def index
    @carpool_groups = CarpoolGroup.includes(:car, :trip).order(month: :desc)
  end

  def new
    @carpool_group = CarpoolGroup.new
    load_form_data
  end

  def create
    @carpool_group = CarpoolGroup.new(carpool_group_params)
    if @carpool_group.save
      redirect_to admin_carpool_groups_path, notice: "Group created."
    else
      load_form_data
      render :new, status: :unprocessable_entity
    end
  end

  def edit
    load_form_data
  end

  def update
    if @carpool_group.update(carpool_group_params)
      redirect_to admin_carpool_groups_path, notice: "Group updated."
    else
      load_form_data
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    @carpool_group.destroy
    redirect_to admin_carpool_groups_path, notice: "Group removed."
  end

  private

  def set_group
    @carpool_group = CarpoolGroup.find(params[:id])
  end

  def load_form_data
    @cars = Car.all.order(:name)
    @trips = Trip.all.order(:name)
  end

  def carpool_group_params
    params.require(:carpool_group).permit(:name, :month, :car_id, :trip_id)
  end
end
