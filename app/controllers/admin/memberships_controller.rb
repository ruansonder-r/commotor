class Admin::MembershipsController < Admin::BaseController
  before_action :set_membership, only: [ :edit, :update, :destroy ]

  def index
    @memberships = Membership.includes(:user, carpool_group: [ :car, :trip ]).order("carpool_groups.name, users.display_name")
  end

  def new
    @membership = Membership.new
    load_form_data
  end

  def create
    @membership = Membership.new(membership_params)
    if @membership.save
      redirect_to admin_memberships_path, notice: "Member added."
    else
      load_form_data
      render :new, status: :unprocessable_entity
    end
  end

  def edit
    load_form_data
  end

  def update
    if @membership.update(membership_params)
      redirect_to admin_memberships_path, notice: "Membership updated."
    else
      load_form_data
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    @membership.destroy
    redirect_to admin_memberships_path, notice: "Member removed."
  end

  private

  def set_membership
    @membership = Membership.find(params[:id])
  end

  def load_form_data
    @users = User.all.order(:display_name)
    @carpool_groups = CarpoolGroup.includes(:car, :trip).order(:name)
  end

  def membership_params
    params.require(:membership).permit(:user_id, :carpool_group_id, :cost_split_percentage)
  end
end
