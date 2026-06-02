from calendar import monthcalendar
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser, OptionalUser
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import LoginRequest
from app.models.commitment import CommitmentStatus
from app.schemas.commitment import CommitmentCreate, CommitmentStatusUpdate, CommitmentUpdate
from app.services.auth_service import AuthService
from app.services.ai_service import AIService
from app.services.commitment_service import (
    CommitmentService,
    status_border_color,
    status_display_color,
)

router = APIRouter(include_in_schema=False)
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _auth_redirect(token: str) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response


def _status_choices() -> list[tuple[str, str]]:
    labels = {
        CommitmentStatus.TO_CHECK: "To check",
        CommitmentStatus.EXPIRED: "Expired",
        CommitmentStatus.DONE: "Done",
        CommitmentStatus.NOT_ACTUAL: "Not actual",
        CommitmentStatus.IDEAS_BACKLOG: "Ideas backlog",
    }
    return [(s.value, labels[s]) for s in CommitmentStatus]


def _template_context(request: Request, user: Any = None, **extra: Any) -> dict:
    ctx = {
        "request": request,
        "user": user,
        "status_choices": _status_choices(),
        "status_colors": {s.value: status_display_color(s) for s in CommitmentStatus},
        "status_borders": {s.value: status_border_color(s) for s in CommitmentStatus},
    }
    ctx.update(extra)
    return ctx


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    return int(value)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: OptionalUser) -> HTMLResponse:
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("auth/login.html", _template_context(request))


@router.post("/login")
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    token = await AuthService(db).authenticate(LoginRequest(email=email, password=password))
    if not token:
        return templates.TemplateResponse(
            "auth/login.html",
            _template_context(request, error="Invalid email or password"),
            status_code=400,
        )
    return _auth_redirect(token.access_token)


@router.get("/logout")
async def logout_page() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/", response_class=HTMLResponse)
async def calendar_home(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
    year: int | None = None,
    month: int | None = None,
    project_id: str | None = None,
    reviewer_id: str | None = None,
) -> HTMLResponse:
    now = datetime.now(UTC)
    year = year or now.year
    month = month or now.month
    parsed_project_id = _parse_optional_int(project_id)
    parsed_reviewer_id = _parse_optional_int(reviewer_id)

    commitments = await CommitmentService(db).list_for_month(
        year, month, project_id=parsed_project_id, reviewer_id=parsed_reviewer_id
    )
    svc = CommitmentService(db)
    projects = await svc.list_projects()
    users = await AuthService(db).list_users()

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    month_label = datetime(year, month, 1, tzinfo=UTC).strftime("%B %Y")

    return templates.TemplateResponse(
        "calendar/index.html",
        _template_context(
            request,
            user=user,
            year=year,
            month=month,
            commitments=commitments,
            projects=projects,
            users=users,
            cal_weeks=monthcalendar(year, month),
            prev_month=prev_month,
            prev_year=prev_year,
            next_month=next_month,
            next_year=next_year,
            month_label=month_label,
            filters={
                "project_id": parsed_project_id,
                "reviewer_id": parsed_reviewer_id,
            },
        ),
    )


async def _commitment_form_context(
    request: Request,
    db: AsyncSession,
    user: Any,
    *,
    commitment=None,
    prefill=None,
    ai_prompt: str = "",
    error: str | None = None,
    ai_message: str | None = None,
) -> dict:
    ai = AIService(db)
    return _template_context(
        request,
        user=user,
        commitment=commitment,
        prefill=prefill,
        ai_prompt=ai_prompt,
        error=error,
        ai_message=ai_message,
        ai_available=ai.is_available,
        projects=await CommitmentService(db).list_projects(),
        users=await AuthService(db).list_users(),
    )


@router.get("/commitments/new", response_class=HTMLResponse)
async def commitment_new(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "commitments/form.html",
        await _commitment_form_context(request, db, user),
    )


@router.post("/commitments/new/ai-fill", response_class=HTMLResponse)
async def commitment_ai_fill(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
    prompt: str = Form(...),
) -> HTMLResponse:
    prefill, err = await AIService(db).parse_commitment_prompt(prompt)
    return templates.TemplateResponse(
        "commitments/form.html",
        await _commitment_form_context(
            request,
            db,
            user,
            prefill=prefill,
            ai_prompt=prompt,
            error=err,
            ai_message="Form filled by AI — review and save." if prefill else None,
        ),
        status_code=400 if err else 200,
    )


@router.post("/commitments/new")
async def commitment_create(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
    title: str = Form(...),
    description: str = Form(""),
    project_id: str = Form(""),
    executor_id: str = Form(""),
    reviewer_id: str = Form(""),
    deadline: str = Form(""),
    status: str = Form(CommitmentStatus.TO_CHECK.value),
):
    parsed_deadline = None
    if deadline.strip():
        parsed_deadline = datetime.fromisoformat(deadline)
        if parsed_deadline.tzinfo is None:
            parsed_deadline = parsed_deadline.replace(tzinfo=UTC)

    try:
        data = CommitmentCreate(
            title=title,
            description=description or None,
            project_id=int(project_id) if project_id else None,
            executor_id=int(executor_id) if executor_id else None,
            reviewer_id=int(reviewer_id) if reviewer_id else None,
            deadline=parsed_deadline,
            status=CommitmentStatus(status),
        )
        created = await CommitmentService(db).create_commitment(data, user.id)
    except Exception as exc:
        return templates.TemplateResponse(
            "commitments/form.html",
            await _commitment_form_context(
                request, db, user, commitment=None, error=str(exc)
            ),
            status_code=400,
        )
    return RedirectResponse(url=f"/commitments/{created.id}", status_code=302)


@router.get("/commitments/{commitment_id}", response_class=HTMLResponse)
async def commitment_detail(
    request: Request,
    commitment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
) -> HTMLResponse:
    item = await CommitmentService(db).get_commitment(commitment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(
        "commitments/detail.html",
        _template_context(request, user=user, commitment=item),
    )


@router.get("/commitments/{commitment_id}/edit", response_class=HTMLResponse)
async def commitment_edit(
    request: Request,
    commitment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
) -> HTMLResponse:
    item = await CommitmentService(db).get_commitment(commitment_id)
    if not item:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "commitments/form.html",
        _template_context(
            request,
            user=user,
            commitment=item,
            projects=await CommitmentService(db).list_projects(),
            users=await AuthService(db).list_users(),
        ),
    )


@router.post("/commitments/{commitment_id}/edit")
async def commitment_update(
    commitment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
    title: str = Form(...),
    description: str = Form(""),
    project_id: str = Form(""),
    executor_id: str = Form(""),
    reviewer_id: str = Form(""),
    deadline: str = Form(""),
    status: str = Form(...),
) -> RedirectResponse:
    parsed_deadline = None
    if deadline.strip():
        parsed_deadline = datetime.fromisoformat(deadline)
        if parsed_deadline.tzinfo is None:
            parsed_deadline = parsed_deadline.replace(tzinfo=UTC)

    data = CommitmentUpdate(
        title=title,
        description=description or None,
        project_id=int(project_id) if project_id else None,
        executor_id=int(executor_id) if executor_id else None,
        reviewer_id=int(reviewer_id) if reviewer_id else None,
        deadline=parsed_deadline,
        status=CommitmentStatus(status),
    )
    item = await CommitmentService(db).update_commitment(commitment_id, data)
    if not item:
        raise HTTPException(status_code=404)
    return RedirectResponse(url=f"/commitments/{commitment_id}", status_code=302)


@router.post("/commitments/{commitment_id}/status")
async def commitment_status(
    commitment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
    status_value: str = Form(..., alias="status"),
) -> RedirectResponse:
    await CommitmentService(db).update_status(
        commitment_id,
        CommitmentStatusUpdate(status=CommitmentStatus(status_value)),
    )
    return RedirectResponse(url=f"/commitments/{commitment_id}", status_code=302)


@router.post("/commitments/{commitment_id}/delete")
async def commitment_delete(
    commitment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: CurrentUser,
) -> RedirectResponse:
    await CommitmentService(db).delete_commitment(commitment_id)
    return RedirectResponse(url="/", status_code=302)
