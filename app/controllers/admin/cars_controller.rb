class Admin::CarsController < Admin::BaseController
  before_action :set_car, only: [ :edit, :update, :destroy ]

  def index
    @cars = Car.all.order(:name)
  end

  def new
    @car = Car.new
  end

  def create
    @car = Car.new(car_params)
    if @car.save
      redirect_to admin_cars_path, notice: "Car added."
    else
      render :new, status: :unprocessable_entity
    end
  end

  def edit
  end

  def update
    if @car.update(car_params)
      redirect_to admin_cars_path, notice: "Car updated."
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    if @car.destroy
      redirect_to admin_cars_path, notice: "Car removed."
    else
      redirect_to admin_cars_path, alert: @car.errors.full_messages.to_sentence
    end
  end

  private

  def set_car
    @car = Car.find(params[:id])
  end

  def car_params
    params.require(:car).permit(:name, :cost_per_km)
  end
end
